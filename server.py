# Coded by Joel Robertson
# VUW 300342674
# 2016

import socket
import select
import sys
import sqlite3

PORT = '5000'
if len(sys.argv) > 1:
    PORT = sys.argv[1]


def run_server():
    """
    Start a server to facilitate the chat between clients.
    The server uses a single socket to accept incoming connections
    which are then added to a list (socket_list) and are listened to
    to receive incoming messages. Messages are then stored in a database
    and are transmitted back out to the clients.
    """

    # Define where the server is running. 127.0.0.1 is the loopback address,
    # meaning it is running on the local machine.
    host = "127.0.0.1"
    port = int(PORT)

    # Create a socket for the server to listen for connecting clients
    server_socket = socket.socket()
    server_socket.bind((host, port))
    server_socket.listen(10)

    # Create a list to manage all of the sockets
    socket_list = [server_socket]

    # Create a dictionary to link between socket IDs and the socket handles
    socket_id_to_handle = {}

    # Create a database to manage chat rooms.
    conn = sqlite3.connect('server.db')
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS user_rooms (room TEXT, socket TEXT, username TEXT)')

    # Start listening for input from both the server socket and the clients
    while True:
        # Try is necessary to catch the keyboard exception.
        try:
            # Monitor all of the sockets in socket_list until something happens
            ready_to_read, ready_to_write, in_error = select.select(socket_list, socket_list, [], 0)

            # When something happens, check each of the ready_to_read sockets

            for sock in ready_to_read:
                # A new connection request received
                if sock == server_socket:
                    # Accept the new socket request
                    sockfd, addr = server_socket.accept()
                    # Add the socket to the list of sockets to monitor
                    socket_list.append(sockfd)
                    # Add the socket to the dictionary linking socket IDs and socket handles.
                    client_id = str(sockfd.getpeername()[1])
                    socket_id_to_handle[client_id] = sockfd
                    # Add the user into the database in default (global) chatroom
                    c.execute('INSERT INTO user_rooms (room, socket, username) values\
                              (\'%s\', \'%s\', \'Anonymous\')' % ('global', client_id))
                    # Log what has happened on the server
                    print("Client (%s, %s) connected" % (addr[0], addr[1]))

                # A message from a client has been received
                else:
                    # Receive and decode the message
                    data = sock.recv(1024)
                    message = data.decode().strip()
                    # If message contains text then process it as a valid message.
                    if message:
                        '''
                        The statements below get all the relevant information about the user who has sent the message
                        and the room they are in. This could be simplified into fewer database queries which would be
                        more efficient.
                        '''
                        current_id = sock.getpeername()[1]
                        # Get the username of current user (could be Anonymous).
                        c.execute('SELECT username FROM user_rooms WHERE socket = \'%s\'' % current_id)
                        current_user = c.fetchone()[0].strip()
                        # Get the room of the current user.
                        c.execute('SELECT room FROM user_rooms WHERE socket = \'%s\'' % current_id)
                        current_room = c.fetchone()[0].strip()
                        # Get a list of all the usernames in the same room as the current user.
                        c.execute('SELECT username FROM user_rooms WHERE room = \'%s\'' % current_room)
                        # Requires conversion from list of tuples to list of strings using sum.
                        room_users = list(sum(c.fetchall(), ()))
                        # Get a list of all the socket IDs in the same room as the current user.
                        c.execute('SELECT socket FROM user_rooms WHERE room = \'%s\'' % current_room)
                        room_ids = list(sum(c.fetchall(), ()))
                        # Calculate the number of users and anonymous users
                        room_num = len(room_users)
                        anon_num = room_users.count("Anonymous")

                        # Print a record of message being received at server console.
                        print("{}: {}".format(current_user, message))

                        # If message starts with /JOIN, change the current user's chat room.
                        if message.startswith("/JOIN"):
                            # Get desired room name from message.
                            desired_room_split = message.split(' ')
                            if len(desired_room_split) < 2:
                                sock.send("Error: No room specified, please try again.".encode())
                                break
                            desired_room = desired_room_split[1]
                            # Update database to reflect user in new room.
                            c.execute('UPDATE user_rooms set room = \'%s\' where socket = \'%s\''
                                      % (desired_room, current_id))
                            sock.send("You are now in room: {}".format(desired_room).encode())

                        # If message starts with /NICK sequence, interpret as request to change username.
                        elif message.startswith('/NICK'):
                            # Get desired username from message.
                            desired_username_split = message.split(' ')
                            if len(desired_username_split) < 2:
                                sock.send("Error: No username specified, please try again.".encode())
                                break
                            desired_username = desired_username_split[1]
                            # If requested username is any variation of anonymous then decline change.
                            if desired_username.lower() == "anonymous":
                                sock.send("Sorry, anonymous is not a valid username.".encode())
                                break
                            # Get list of all usernames in all chat rooms (with string and list conversion).
                            c.execute('SELECT username FROM user_rooms')
                            current_users = str(list(sum(c.fetchall(), ())))
                            # If the desired username is already in use, decline change. Otherwise, update database.
                            if desired_username in current_users:
                                sock.send("Sorry, {} is already a username.".format(desired_username).encode())
                            else:
                                c.execute('UPDATE user_rooms set username = \'%s\' where \
                                          socket = \'%s\'' % (desired_username, current_id))
                                sock.send("Username successfully changed to {}".format(desired_username).encode())

                        # If message starts with /WHO, send the current user a list of all current chat usernames.
                        elif message.startswith('/WHO'):
                            # String to send to user is called who and has all relevant information added to it here
                            who = "There are currently {} users connected in room {} ({} anonymous):\n" \
                                .format(room_num, current_room, anon_num)
                            # Insert all of the current room usernames into the message back to the client.
                            for username in room_users:
                                # Do not send the anonymous usernames back (as they cannot be private messaged)
                                if username != "Anonymous":
                                    who += "\t{}\n".format(username)
                            # Tell the user what their current username is
                            if current_user == "Anonymous":
                                who += "You are currently anonymous"
                            else:
                                who += "Your username is {}".format(current_user)
                            sock.send(who.encode())

                        # If message starts with /MSG, send the message only to a specified username (if in same room).
                        elif message.startswith('/MSG'):
                            # Get desired recipient from message.
                            user_to_split = message.split(' ')
                            # If user has used wrong syntax
                            if len(user_to_split) < 2:
                                sock.send("Error: No recipient specified, please try again.".encode())
                                break
                            user_to = user_to_split[1]
                            new_message = message.split(user_to)[1].lstrip()
                            # If the desired recipient
                            if user_to in room_users:
                                sock.send("From you to {}: {}".format(user_to, new_message).encode())
                                # Get the socket ID and the socket handle then send the message to recipient.
                                c.execute('SELECT socket FROM user_rooms WHERE username = \'%s\'' % user_to)
                                socket_to = c.fetchone()[0]
                                client = socket_id_to_handle.get(socket_to)
                                client.send("From {} to you: {}".format(current_user, new_message).encode())
                            else:
                                sock.send("Sorry, {} is not an active user in room {}.".format(
                                    user_to, current_room).encode())

                        # This is not a required part of the assignment. This can list all of the different active
                        # chatrooms and list the user's current room.
                        elif message.startswith('/WHERE'):
                            # Get the set of rooms which are currently in the database
                            c.execute('SELECT room FROM user_rooms')
                            rooms = set(sum(c.fetchall(), ()))
                            where = "There are currently {} rooms in use:\n".format(len(rooms))
                            # Insert all of the current rooms into the message back to the client.
                            for room in rooms:
                                where += "\t{}\n".format(room)
                            where += "You are currently in room {}".format(current_room)
                            sock.send(where.encode())

                        # The message is for all of the current chatroom members.
                        else:
                            # Get all of the socket_ids of users in the current room.
                            c.execute('SELECT socket FROM user_rooms WHERE room = \'%s\'' % current_room)
                            for socket_id_to in room_ids:
                                # Get the socket handle.
                                client = socket_id_to_handle.get(socket_id_to)
                                # If the client has been listed as ready-to-write-to then send the message
                                if client in ready_to_write:
                                    client.send("{} in {}: {}".format(current_user, current_room, message).encode())
                    # If message is empty then client disconnected so close the socket and remove DB and dict records
                    else:
                        addr = sock.getpeername()
                        print("Client (%s, %s) disconnected" % (addr[0], addr[1]))
                        c.execute('DELETE FROM user_rooms WHERE socket = \'%s\'' % addr[1])
                        socket_list.remove(sock)
        # If program is ended with Ctrl-C then close all of the connections.
        except KeyboardInterrupt:
            for socket_handle in socket_list:
                socket_handle.close()
                print("Error: Server disconnected")
                return


if __name__ == '__main__':
    run_server()
