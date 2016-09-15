# Coded by Joel Robertson
# VUW 300342674
# 2016

import sys
import socket
import select

PORT = '5000'
if len(sys.argv) > 1:
    PORT = sys.argv[1]

sys._clear_type_cache()

def run_client():
    """
    Run the client. This should listen for input text from the user
    and send messages to the server. Responses from the server should
    be printed to the console.
    """
    # Specify where the server is to connect to
    server_address = '127.0.0.1'
    port = int(PORT)
    
    # Create a socket and connect to the server
    client_socket = socket.socket()
    client_socket.connect((server_address, port))
    socket_list = [sys.stdin, client_socket]

    # Log that it has connected to the server
    print('Connected to chat server.')
    print('Type here to send messages:')

    # Start listening for input and messages from the server
    while True:        
        # Listen to the sockets (and command line input) until something happens
        try:
            ready_to_read, ready_to_write, in_error = select.select(socket_list, [], [], 0)

            # When one of the inputs are ready, process the message
            for sock in ready_to_read:
                # The server has sent a message
                if sock == client_socket:
                    # Receive the message from the server and decode it to a string (with no leading whitespace)
                    data = sock.recv(1024)
                    message = data.decode().strip()
                    # If message contains any data then print the message.
                    if message:
                        print(message)
                    # If message contains no data then the server has disconnected, so end the program
                    else:
                        print("Error: Server disconnected")
                        return
                # The user entered a message
                else:
                    msg = sys.stdin.readline()
                    # Send the message to the server
                    client_socket.send(msg.encode())
        # If Ctrl-C is pressed then close the connection and end the program
        except KeyboardInterrupt:
            client_socket.close()
            print("Client disconnected")
            return
        
if __name__ == '__main__':
    run_client()
