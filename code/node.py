from raise_p2p import query


class Node:
	def __init__(self, host_ip):
		self.data = {'clients': [], 'services': [], 'datas': [], 'tokens': []}

		self.update_data()

	def update_data(self):
		self.data['clients'] = query.get_client()[0]
		self.data['services'] = query.get_service()[0]
		self.data['datas'] = query.get_data()[0]
		self.data['tokens'] = query.get_token()[0]

	def data_by_ip(self, ip):
		tmp_data = {'clients': [], 'services': [], 'datas': [], 'tokens': []}
		tmp_data['clients'] = query.get_client(ip=ip)[0]
		tmp_data['services'] = query.get_service(ip=ip)[0]
		tmp_data['datas'] = query.get_data(ip=ip)[0]
		tmp_data['tokens'] = query.get_token(ip=ip)[0]

		return tmp_data

	def delete_by_ip(self, ip):
		return query.delete_data(ip=ip)
