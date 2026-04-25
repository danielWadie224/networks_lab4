from rdt_protocol import RDTProtocol
import time

def run_comprehensive_test():
    server_addr = ('127.0.0.1', 12345)
    
    # 1. Test GET request
    print("\n=== TEST 1: GET index.html ===")
    rdt = RDTProtocol(probability_loss=0.05, probability_corrupt=0.05)
    if rdt.connect(server_addr):
        request = "GET /index.html HTTP/1.0\r\nHost: localhost\r\n\r\n"
        rdt.rdt_send(request.encode(), server_addr)
        response, _ = rdt.rdt_rcv()
        print(f"Response:\n{response.decode() if response else 'None'}")
        rdt.close(server_addr)
    
    time.sleep(1)

    # 2. Test POST request
    print("\n=== TEST 2: POST data ===")
    rdt = RDTProtocol(probability_loss=0.05, probability_corrupt=0.05)
    if rdt.connect(server_addr):
        post_body = "This is some test data sent via POST!"
        request = (f"POST /test.txt HTTP/1.0\r\n"
                   f"Content-Length: {len(post_body)}\r\n"
                   f"\r\n"
                   f"{post_body}")
        rdt.rdt_send(request.encode(), server_addr)
        response, _ = rdt.rdt_rcv()
        print(f"Response:\n{response.decode() if response else 'None'}")
        rdt.close(server_addr)

    time.sleep(1)

    # 3. Test False Checksum Simulation
    print("\n=== TEST 3: False Checksum Simulation ===")
    rdt = RDTProtocol(probability_loss=0, probability_corrupt=0)
    if rdt.connect(server_addr):
        print("Simulating a bad checksum on the next packet...")
        rdt.simulate_false_checksum()
        request = "GET /index.html HTTP/1.0\r\n\r\n"
        # The first attempt will have a bad checksum, triggering a timeout/retransmit
        rdt.rdt_send(request.encode(), server_addr)
        response, _ = rdt.rdt_rcv()
        print("Success after retransmission!")
        rdt.close(server_addr)

if __name__ == "__main__":
    run_comprehensive_test()
