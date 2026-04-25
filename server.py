# The server receives the request using our RDT layer
request_data, client_addr = rdt_instance.rdt_rcv()
request_str = request_data.decode()

# Logic to extract the filename (e.g., index.html)
filename = request_str.split()[1].strip("/")

try:
    with open(filename, "rb") as f:
        content = f.read()
    # Create a success response
    response = b"HTTP/1.0 200 OK\r\n\r\n" + content
except FileNotFoundError:
    # Create an error response
    response = b"HTTP/1.0 404 NOT FOUND\r\n\r\n"

# Send it back reliably
rdt_instance.rdt_send(response, client_addr)