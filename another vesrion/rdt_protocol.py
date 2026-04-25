import socket
import struct
import hashlib
import random

class RDTProtocol:
    def __init__(self, is_server=False, port=8080):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) 
        self.sock.settimeout(2.0) # Standard timeout for retransmission [cite: 11]
        self.seq_num = 0 # Sequence number for Stop-and-Wait [cite: 35, 43]
        if is_server:
            self.sock.bind(('', port))

    def compute_checksum(self, data_bytes):
        """Calculates MD5 hash of the header and data[cite: 10, 37, 41]."""
        return hashlib.md5(data_bytes).digest()

    def make_pkt(self, seq_num, is_ack, is_syn=0, is_fin=0, data=b''):
        """Packs sequence number, flags (SYN, ACK, FIN), checksum, and payload[cite: 37, 43]."""
        # Step 1: Pack header values for checksum calculation
        temp_header = struct.pack('iiii', seq_num, is_ack, is_syn, is_fin)
        packet_checksum = self.compute_checksum(temp_header + data) 
        
        # Step 2: Pack final header with the 16-byte MD5 hash
        final_header = struct.pack('iiii16s', seq_num, is_ack, is_syn, is_fin, packet_checksum)
        return final_header + data
    
    def parse_pkt(self, packet):
        """Unpacks the binary data into header fields and payload[cite: 33]."""
        header = packet[:32]
        data = packet[32:]
        seq_num, is_ack, is_syn, is_fin, packet_checksum = struct.unpack('iiii16s', header)
        return seq_num, is_ack, is_syn, is_fin, packet_checksum, data

    def is_corrupt(self, packet):
        """Verifies the checksum; drops packet if it doesn't match[cite: 38]."""
        seq, ack, syn, fin, received_checksum, data = self.parse_pkt(packet)
        temp_header = struct.pack('iiii', seq, ack, syn, fin)
        return received_checksum != self.compute_checksum(temp_header + data)

    def simulate_chaos(self, packet, loss_rate=0.1, corruption_rate=0.1):
        """Simulates packet loss and corruption for testing[cite: 39, 42]."""
        if random.random() < loss_rate:
            print("!!! Packet Lost (Simulated) !!!")
            return None 
        if random.random() < corruption_rate:
            print("!!! Packet Corrupted (Simulated) !!!")
            packet = bytearray(packet)
            packet[-1] = packet[-1] ^ 0xFF # Flip a bit to fail checksum [cite: 39]
            return bytes(packet)
        return packet

    # --- Connection Management  ---

    def accept(self):
        """Server-side: Executes the 3-way handshake."""
        print("Server: Waiting for SYN...")
        while True:
            self.sock.settimeout(None) 
            packet, addr = self.sock.recvfrom(2048)
            if not self.is_corrupt(packet):
                seq, ack, syn, fin, _, _ = self.parse_pkt(packet)
                if syn == 1:
                    print(f"Server: Received SYN from {addr}")
                    syn_ack = self.make_pkt(seq_num=0, is_ack=1, is_syn=1)
                    self.sock.settimeout(2.0)
                    while True:
                        self.sock.sendto(syn_ack, addr)
                        try:
                            resp, _ = self.sock.recvfrom(2048)
                            if not self.is_corrupt(resp):
                                _, a_ack, _, _, _, _ = self.parse_pkt(resp)
                                if a_ack == 1:
                                    print("Server: Handshake Complete (ESTABLISHED)")
                                    self.seq_num = 0
                                    return addr
                        except socket.timeout:
                            print("Server: Resending SYN-ACK...")

    def connect(self, server_addr):
        """Client-side: Executes the 3-way handshake."""
        syn_pkt = self.make_pkt(seq_num=0, is_ack=0, is_syn=1)
        while True:
            print("Client: Sending SYN...")
            self.sock.sendto(syn_pkt, server_addr)
            try:
                resp, addr = self.sock.recvfrom(2048)
                if not self.is_corrupt(resp):
                    seq, ack, syn, fin, _, _ = self.parse_pkt(resp)
                    if ack == 1 and syn == 1:
                        print("Client: Received SYN-ACK")
                        final_ack = self.make_pkt(seq_num=1, is_ack=1)
                        self.sock.sendto(final_ack, addr)
                        self.seq_num = 0
                        return True
            except socket.timeout:
                print("Client: Handshake timeout, retrying...")

    # --- Data Transfer (Stop-and-Wait)  ---

    def rdt_send(self, data, dest_addr):
        """Sends data reliably and waits for ACK before toggling sequence number[cite: 35, 40]."""
        packet = self.make_pkt(self.seq_num, is_ack=0, data=data)
        while True:
            p = self.simulate_chaos(packet)
            if p: self.sock.sendto(p, dest_addr)
            try:
                ack_packet, _ = self.sock.recvfrom(2048)
                if not self.is_corrupt(ack_packet):
                    rcv_seq, is_ack, _, _, _, _ = self.parse_pkt(ack_packet)
                    if is_ack == 1 and rcv_seq == self.seq_num:
                        self.seq_num = 1 - self.seq_num # Toggle seq 
                        break
            except socket.timeout:
                print(f"Timeout! Retransmitting seq {self.seq_num}...") 

    def rdt_rcv(self):
        """Listens for packets, drops corrupted ones, and returns data[cite: 38]."""
        while True:
            packet, addr = self.sock.recvfrom(2048)
            if self.is_corrupt(packet):
                print("Corrupt packet dropped.") 
                continue
            
            rcv_seq, is_ack, is_syn, is_fin, _, data = self.parse_pkt(packet)
            if is_fin == 1: return b'', addr, True

            if rcv_seq == self.seq_num:
                ack_pkt = self.make_pkt(self.seq_num, is_ack=1)
                self.sock.sendto(ack_pkt, addr)
                self.seq_num = 1 - self.seq_num
                return data, addr, False
            else:
                # Duplicate packet handling 
                ack_pkt = self.make_pkt(rcv_seq, is_ack=1)
                self.sock.sendto(ack_pkt, addr)

    def close(self, dest_addr):
        """Connection teardown using FIN flag."""
        fin_pkt = self.make_pkt(self.seq_num, is_ack=0, is_fin=1)
        self.sock.sendto(fin_pkt, dest_addr)
        print("Connection Closed.")