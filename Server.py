import sys, socket, re

connected = True

def parse501(message,token,parsedText,socket):
    mail = re.match("MAIL\s+FROM:\s*<([a-zA-Z0-9!#$%&'*+/=?~^_`}{|~-]{1,61}@(?:(?:[a-zA-Z])(?:[a-zA$
    rcpt = re.match("RCPT\s+TO:\s*<([a-zA-Z0-9!#$%&'*+/=?~^_`}{|~-]{1,61}@(?:(?:[a-zA-Z])(?:[a-zA-Z$
    data = re.match('DATA\s*$', message)

    if(token not in {'mail','rcpt','data'}):
        return True

    if(token == 'mail'):
        if mail:
            socket.send('250 OK\r\n'.encode())
            parsedText.append(mail.group(0))
            return False
        else:
            socket.send('501 Syntax error in parameters or arguments\r\n'.encode())
            return True
    elif(token == 'rcpt'):
        if rcpt:
            socket.send('250 OK\r\n'.encode())
            parsedText.append(rcpt.group(0))
            parsedText.append(rcpt.group(1))
            return False
        else:
            socket.send('501 Syntax error in parameters or arguments\r\n'.encode())
            return True
    elif(token == 'data'):
        if data:
            socket.send('354 Start mail input; end with . on a line by itself\r\n'.encode())
            parsedText.append(data.group(0))
            return False
        else:
            socket.send('501 Syntax error in parameters or arguments\r\n'.encode())
            return True

def parseToken(token, message, socket):
    global connected
    if connected == False:
        return False

    if(token not in {'mail','rcpt','data'}):
        return False

    mail = re.match('MAIL\s+FROM:\s*', message)
    rcpt = re.match('RCPT\s+TO:\s*', message)
    data = re.match('DATA\s*', message)

    if(token == 'mail'):
        if(rcpt or data):
            socket.send('503 Bad sequence of commands\r\n'.encode())
            return False
        elif(mail):
            return True

    elif(token == 'data'):
        if(rcpt or mail):
            socket.send('503 Bad sequence of commands\r\n'.encode())
            return False
        elif(data):
            return True

    elif(token == 'rcpt'):
        if(mail or data):
            socket.send('503 Bad sequence of commands\r\n'.encode())
            return False
        elif(rcpt):
            return True

    socket.send('500 Syntax error: command unrecognized\r\n'.encode())
    return False

def parseInput(inputSocket):
    global connected
    try:
        message = inputSocket.recv(4096).decode()
        sys.stdout.write(message)
        if(message == 'QUIT\r\n'):
            inputSocket.send(f'221 {socket.getfqdn()} closing connection\r\n'.encode())
            connected = False
            inputSocket.close()
        return message
    except socket.error as err:
        inputSocket.close()
        connected = False

def parseMail(parsedText, socket):
    global connected
    while(True):
        message = parseInput(socket)
        if not connected:
            return False
        if not parseToken('mail', message, socket):
            continue
        else:
            if not parse501(message,'mail',parsedText, socket):
                return True
            else:
                continue

def parseRcpt(parsedText,socket):
    global connected
    while(True):
        message = parseInput(socket)
        if not connected:
            return False
        #parse if token is out of order
        if not parseToken('rcpt', message, socket):
            continue
        else:
            if not parse501(message, 'rcpt',parsedText, socket):
                return True
            else:
                continue

def parseData(parsedText, socket):
    global connected
    while(True):
        message = parseInput(socket)
        if not parseToken('data', message, socket):
            continue
        else:
            if not parse501(message,'data',parsedText, socket):
                messageData = []
                EOF = False
                while not EOF:
                    inputMessage = socket.recv(4096).decode()
                    message = inputMessage.splitlines()
                    for line in message:
                        print(line, end = '\r\n')
                        messageData.append(line)
                        if(line =='.\r\n'or line =='.'):
                            socket.send('250 OK\r\n'.encode())
                            EOF = True
                            break
                parsedText.append(messageData)
                return True
            else:
                continue

def writer(parsedText):
    domain = parsedText[2].split('@',1)[1]
    # new file's name doesnt need angle brackets
    fileName = "forward/"+ domain
    # a+ creates a new file if one doesnt already exist
    newFile = open((fileName), "a+")
    newFile.write(parsedText[0])
    newFile.write(parsedText[1])
    newFile.write(parsedText[3])
    for i in range(len(parsedText[4])):
        receiver = parsedText[4][i]
        newFile.write(receiver+ "\r\n")

def mail(socket):
    temp = []
    while(True):
        # parsedText[0] = MAIL, parsedText[1] = RCPT, parsedText[3] = DATA
        parsedText = []
        mailFromstatus = parseMail(parsedText, socket)
        if mailFromstatus:
            rcptStatus = parseRcpt(parsedText, socket)
            if rcptStatus:
                parseData(parsedText, socket)
                temp.append(parsedText)
                writer(parsedText)
                if not connected:
                    return False
        else:
            if not connected:
                return False
            continue
    return False

def connect(csocket):
    global connected
    try:
        host = socket.getfqdn()
        csocket.send(f"220 {host}\r\n".encode())
        while(True):
            parsed = parseInput(csocket)
            if connected:
                if(parsed[0:5] == 'HELO '):
                    parsed = re.match('HELO\s+((?:(?:[a-zA-Z])(?:[a-zA-Z0-9-])*\.)+(?:[a-zA-Z])(?:[$
                    if parsed:
                        serverHand = f"250 Hello {parsed.group(1)} pleased to meet you\r\n"
                        csocket.send(serverHand.encode())
                        return True
                    else:
                        csocket.send('501 Syntax error in parameters or arguments\r\n'.encode())
                        continue
                else:
                    csocket.send('500 Syntax error: command unrecognized\r\n'.encode())
                    continue
            else:
                return False

    except socket.error as err:
        print(err)
        csocket.close()
        connected = False


def server():
    global connected
    #port = int(input())
    port = int(sys.argv[1])

    try:
        serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    except socket.error as err:
        print(err)

    try:
        serversocket.bind((socket.getfqdn(), port))
    except socket.error as err:
        print(err)
        quit()

    #listen with a max queue of 5
    serversocket.listen(5)

    while True:
        csocket, address = serversocket.accept()
        connected = True
        startProcessing = connect(csocket)

        if (startProcessing == True):
            mail(csocket)

server()

# todo:
#   create a new file
#   remove string splitting and replace with a better way
#   implement regex to decrease overhead per TA's advice
#   create message abstractions
#   clean up code