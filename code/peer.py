from raise_p2p.p2p.node import Node

import threading
import struct
import socket
import time
import json

SHOW_MESSAGE = "http://localhost:5000/message"


class Peer(Node):
	"""Peer node of a P2P network.

	IPv4 (AF_INET) protocol with TCP (SOCK_STREAM).

	Args:
		host_ip (str): Host IP from host name.
	"""
	PORT = 12666

	def __init__(self, host_ip, socketio):
		self.HOST = host_ip
		self.stop = False
		self.socketio = socketio
		self.socketio.emit('message', {'data': 'Peer iniciado.'},
							namespace='/message')
		self.node = Node(host_ip)

		self.commands = {'BACKUP': self.backup,
						'RESTORE': self.restore,
						'BACKUP_RCV': self.backup_rcv,
						'RESTORE_RCV': self.restore_rcv}

		self.init_socket()

	def init_socket(self):
		"""Start TCP server socket on port 12666.

		Queue up 10 connect requests before refusing outside connections.
		"""
		#
		self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		# SO_REUSEADDR : the port 12666 will be immediately reusable after
		# the socket is closed
		self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		self.socket.bind((self.HOST, self.PORT))
		self.socket.listen(10)
		self.socketio.emit('message', {'data': 'Socket iniciado.'},
							namespace='/message')

	def run(self):
		while not self.stop:
			client_conn, client_addr = self.socket.accept()

			self.socketio.emit('ip_client', str(client_addr[0]),
								namespace='/client')

			# Receive data in small chunks and retransmit it
			rcv_data = threading.Thread(target=self.handle_client,
										args=(client_conn, client_addr))
			rcv_data.start()

		self.close()

	def handle_client(self, sckt, address):
		peer_name = sckt.getpeername()
		msg = f'Connected {peer_name}'
		self.socketio.emit('message', {'data': msg}, namespace='/message')

		while True:
			# receive command, then data from backup or restore
			data_rcv = self.read(sckt)
			if 'command' in data_rcv:
				data = data_rcv['command']
				msg = f'Mensagem recebida : {data}'
				self.socketio.emit('message', {'data': msg},
									namespace='/message')
				# send data to backup_rcv or restore_rcv
				self.commands.get(data.upper(),
						lambda x: print(f'Command {data} not found.'))(sckt)

		sckt.close()

		print(f'Disconnecting {peer_name}')

	def send_to_peer(self, host, command):
		sckt = self.peer_connection(host)

		# send data from backup or restore
		self.commands.get(command.upper(),
				lambda x: print(f'Command {command} not found.'))(sckt)

		sckt.close()

	def backup_rcv(self, sckt):
		print(f'Peer try to read from backup_rcv...')
		data_rcv = self.read(sckt)

		if not data_rcv:
			msg = 'DADOS NÃO FORAM RECEBIDOS'
		else:
			msg = 'DADOS RECEBIDOS DO BACKUP'
			self.socketio.emit('backup_client', {'data': data_rcv},
							namespace='/client')

		print(msg)
		self.socketio.emit('message', {'data': msg}, namespace='/message')


	def backup(self, sckt):
		msg = 'CARREGANDO DADOS DO BACKUP...'
		print(msg)
		self.socketio.emit('message', {'data': msg}, namespace='/message')

		if self.send(sckt, {'command': 'BACKUP_RCV'}):
			print(f'Peer sent BACKUP_RCV...')

		if self.node.data and self.send(sckt, self.node.data):
			msg = 'DADOS ENVIADOS COM SUCESSO'
		else:
			msg = 'DADOS NÃO FORAM ENVIADOS..'

		print(msg)
		self.socketio.emit('message', {'data': msg}, namespace='/message')

	def restore_rcv(self, sckt):
		print(f'Peer try to read from restore_rcv...')
		data_rcv = self.read(sckt)

		if not data_rcv:
			msg = 'DADOS NÃO FORAM RECEBIDOS'
		else:
			msg = 'DADOS RECEBIDOS DO RESTORE'
			self.socketio.emit('restore_client', {'data': data_rcv},
								namespace='/client')

		print(msg)
		self.socketio.emit('message', {'data': msg}, namespace='/message')

	def restore(self, sckt):
		msg = 'CARREGANDO DADOS...'
		self.socketio.emit('message', {'data': msg}, namespace='/message')

		if self.send(sckt, {'command': 'RESTORE_RCV'}):
			print(f'Peer sent RESTORE_RCV...')

		ip, port = sckt.getpeername()
		data = self.node.data_by_ip(ip=ip)

		if self.send(sckt, data) and data:
			msg = 'DADOS DO RESTORE ENVIADOS!'

			print(msg)
			self.socketio.emit('message', {'data': msg}, namespace='/message')

			if self.node.delete_by_ip(ip=ip):
				msg = f'DADOS DO IP {ip} REMOVIDOS'
			else:
				msg = f'NÃO HÁ DADOS PARA REMOVER DO {ip}'
		else:
			print("Peer couldn't send restore...")
			msg = 'DADOS NÃO FORAM ENVIADOS NEM REMOVIDOS..'

		print(msg)
		self.socketio.emit('message', {'data': msg}, namespace='/message')

	def peer_connection(self, host, sock=None):
		if not sock:
			client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			not_connect = True

			while not_connect:
				try:
					client_socket.connect((host, self.PORT))
				except:
					print('Trying to connect again...')
					time.sleep(1)
				else:
					not_connect = False
		else:
			client_socket = sock

		return client_socket

	def send(self, sckt, data):
		try:
			serialized = json.dumps(data)
		except (TypeError, ValueError) as e:
			raise Exception('You can only send JSON-serializable data')
		# send the length of the serialized data first
		sckt.send(b'%d\n' % len(serialized))
		# send the serialized data
		sckt.sendall(serialized.encode())

		return True

	def read(self, sckt):
		# read the length of the data, letter by letter until we reach EOL
		length_str = ''
		char = sckt.recv(1).decode()

		while char != '\n':
			length_str += char
			char = sckt.recv(1).decode()
		total = int(length_str)

		# use a memoryview to receive the data chunk by chunk efficiently
		view = memoryview(bytearray(total))
		next_offset = 0

		while total - next_offset > 0:
			recv_size = sckt.recv_into(view[next_offset:], total - next_offset)
			next_offset += recv_size
		try:
			deserialized = json.loads(view.tobytes())
		except (TypeError, ValueError) as e:
			raise Exception('Data received was not in JSON format')

		return deserialized

	def close(self):
		"""Close TCP server socket on port 12666.
		"""
		self.socket.close()
