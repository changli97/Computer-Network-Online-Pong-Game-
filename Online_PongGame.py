import curses
import random
import time
import logging
import socket
import threading
import sys


def initCurses():
    global win
    curses.noecho()
    curses.cbreak()

    curses.curs_set(0)

    win = curses.newwin(HEIGHT, WIDTH)
    win.keypad(True)
    win.box(0, 0)
    win.refresh()
    win.nodelay(True)
    curses.use_default_colors()
    for i in range(0, curses.COLORS):
        curses.init_pair(i, i, -1)


def reset():
    """
    Return ball and paddles to starting positions
    Horizontal direction of the ball is randomized
    """
    global ballX, ballY, padLY, padRY, dx, dy, scoreL, scoreR, run_type
    ballX = int(WIDTH / 2)
    padLY = padRY = ballY = int(HEIGHT / 2)
    dx = dx or 1
    dy = 0
    # Draw to reset everything visually
    draw(ballX, ballY, padLY, padRY, scoreL, scoreR)


def draw(ballX, ballY, padLY, padRY, scoreL, scoreR):
    """
    Draw the current game state to the screen
    ballX: X position of the ball
    ballY: Y position of the ball
    padLY: Y position of the left paddle
    padRY: Y position of the right paddle
    scoreL: Score of the left player
    scoreR: Score of the right player
    """
    win.clear()
    win.border()
    # Center line
    for i in range(1, HEIGHT, 2):
        win.addch(i, 21, '|', curses.color_pair(1))
    # Score
    win.addstr(1,  int(WIDTH / 2) - 3, f'{scoreL:2d}', curses.color_pair(2))
    win.addstr(1,  int(WIDTH / 2) + 1, f'{scoreR:2d}', curses.color_pair(2))
    # Ball
    win.addch(ballY, ballX, '#', curses.color_pair(2))
    # Paddle
    for i in range(1, HEIGHT-1, 1):
        if i > padRY+2 or i < padRY-2:
            win.addch(i, PADRX, ' ', curses.color_pair(2))
        else:
            win.addch(i, PADRX, '#', curses.color_pair(2))
    for i in range(1, HEIGHT-1, 1):
        if i > padLY+2 or i < padLY-2:
            win.addch(i, PADLX, ' ', curses.color_pair(2))
        else:
            win.addch(i, PADLX, '#', curses.color_pair(2))
    # Print the virtual window (win) to the screen
    win.refresh()


def countdown(message):
    """
    Display a message with a 3 second countdown
    This method blocks for the duration of the countdown
    message: The text to display during the countdown
    """
    global lock, scoreR, scoreL, max_rounds
    h = 4
    w = len(message) + 4
    # , (LINES - h) / 2, (COLS - w) / 2);
    popup = curses.newwin(h, w, int((HEIGHT-h) / 2), int((WIDTH-w) / 2))
    popup.box(0, 0)
    popup.addstr(1, 2, message)

    if (scoreR + scoreL) >= max_rounds:
        popup.refresh()
        return
    for countdown in range(3, 0, -1):
        popup.addstr(2, int(w/2), f"{countdown}")
        popup.refresh()
        time.sleep(1)
    popup.clear()
    popup.refresh()
    popup.erase()
    padLY = padRY = int(HEIGHT / 2)


def listenInput(win):
    """
    Listen to keyboard input
    According to run_type to updates global pad positions
    Send location to another client
    """
    global padLY, padRY, ACTIVE, run_type, sock, server_address, client_address
    while ACTIVE:
        key = win.getch()
        curses.flushinp()

        if key == curses.KEY_UP or key == ord('w'):
            if run_type == 'server':
                padRY -= 1
                sock.sendto(b'RW', client_address)
            else:
                padLY -= 1
                sock.sendto(b'LW', server_address)
        elif key == curses.KEY_DOWN or key == ord('s'):
            if run_type == 'server':
                padRY += 1
                sock.sendto(b'RS', client_address)
            else:
                padLY += 1
                sock.sendto(b'LS', server_address)
        time.sleep(0.2)


def tock():
    """
    Perform periodic game functions:
    1. Move the ball
    2. Detect collisions
    3. Detect scored points and react accordingly
    4. Draw updated game state to the screen
    """
    global ballX, ballY, padLY, padRY, dx, dy, scoreL, scoreR, max_rounds
    # Move the ball
    ballX += dx
    ballY += dy

    # Check for paddle collisions
    # padY is y value of closest paddle to ball
    if ballX < WIDTH / 2:
        padY = padLY
        colX = PADLX + 1
    else:
        padY = padRY
        colX = PADRX - 1
    # colX is x value of ball for a paddle collision
    if ballX == colX and abs(ballY - padY) <= 2:
        # Collision detected!
        dx *= -1
        # Determine bounce angle
        if ballY < padY:
            dy = -1
        elif ballY > padY:
            dy = 1
        else:
            dy = 0
    # Check for top/bottom boundary collisions
    if ballY == 1:
        dy = 1
    elif ballY == HEIGHT - 2:
        dy = -1

    # Score points
    if ballX == 0:
        scoreR = (scoreR + 1) % 100
        dx = 1
        reset()
        # Judge if game is over
        if (scoreR + scoreL) < max_rounds:
            countdown("SCORE -->")
        else:
            countdown("GAME OVER")
    elif ballX == WIDTH - 1:
        scoreL = (scoreL + 1) % 100
        dx = -1
        reset()
        # Judge if game is over
        if (scoreR + scoreL) < max_rounds:
            countdown("<-- SCORE")
        else:
            countdown("GAME OVER")
    # Finally, redraw the current state
    else:
        draw(ballX, ballY, padLY, padRY, scoreL, scoreR)


def recv_operation():
    global ACTIVE, sock, padLY, padRY
    while ACTIVE:
        data = sock.recvfrom(1024)
        # According to message from another client to set pad location
        if data[0] == b'RW':
            padRY -= 1
        elif data[0] == b'LW':
            padLY -= 1
        elif data[0] == b'RS':
            padRY += 1
        elif data[0] == b'LS':
            padLY += 1


def main(stdscr):
    global win, ACTIVE, refresh, max_rounds, scoreL, scoreR

    initCurses()
    reset()
    countdown("Starting Game")

    thread1 = threading.Thread(name='daemon', target=listenInput, args=(win, ))
    # New thread for message receive
    thread2 = threading.Thread(target=recv_operation)
    thread1.setDaemon(True)
    thread2.setDaemon(True)
    thread1.start()
    thread2.start()

    while True:
        if (scoreL + scoreR) >= max_rounds:
            break
        before = time.time()
        tock()
        after = time.time()
        toSleep = refresh - (after - before)
        if toSleep > refresh:
            toSleep = refresh
        if toSleep > 0:
            time.sleep(toSleep)
        else:
            time.sleep(refresh/2)

    time.sleep(5)
    ACTIVE = False
    thread1.join()
    thread2.join()
    curses.nocbreak()
    win.keypad(0)
    curses.echo()
    curses.endwin()
    sys.exit()


if __name__ == '__main__':
    args = sys.argv
    option = args[1]
    port = int(args[2])
    run_type = 'server'
    client_address = ''
    server_address = ''
    # new udp socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # Judge the starting mode
    if option == '--host':
        # server
        # set difficulty level
        difficulty = input("Please select the difficulty level (easy, medium or hard): ")
        # set maximum number of rounds
        max_rounds = int(input("Please enter the maximum number of rounds to play: "))
        # new udp server
        sock.bind(('student00.ischool.illinois.edu', port))
        print(f"Waiting for challengers on port {port}")
        while True:
            msg, client_address = sock.recvfrom(1024)
            print(msg)
            print(msg.decode())
            if msg.decode() == 'Join':
                # challenger join game, start
                sock.sendto(f'Start {difficulty} {max_rounds}'.encode(), client_address)
                # game start
                break
    else:
        # client
        run_type = 'client'
        server_address = (option, port)
        sock.sendto(b'Join', server_address)
        while True:
            msg, server_address = sock.recvfrom(1024)
            print(msg.decode())
            msg = msg.decode()
            if msg.startswith('Start'):
                # Get difficulty level
                difficulty = msg.split(' ')[1]
                # Get maximum number of rounds
                max_rounds = int(msg.split(' ')[2])
                # game start
                break
    # new win
    HEIGHT = 21
    WIDTH = 43
    PADLX = 1
    PADRX = WIDTH - 2
    # Position of ball
    ballX = ballY = 0
    # Movement of ball
    dx = dy = 0
    # Position of paddles
    padLY = padRY = 0
    # Player scores
    scoreL = scoreR = 0
    # thread status
    ACTIVE = True

    if difficulty.lower() == "easy":
        refresh = 0.08
    elif difficulty.lower() == "medium":
        refresh = 0.04
    elif difficulty.lower() == "hard":
        refresh = 0.02
    curses.wrapper(main)
