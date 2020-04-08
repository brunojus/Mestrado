from flask import Flask, Response, render_template, jsonify, request, abort,\
                  Blueprint, g
from .validation import JsonValidation, ArgsValidation
from .report import LogReport
from pymongo import errors
import logging
import json
import sys
import configparser
from bson import ObjectId
import datetime
import time

# Função que substitui o aggregate de service
def service_aggregate():
    responses = list(g.db.service_collection.find())
                
    for service in responses:
        datas = list(g.db.data_collection.aggregate([
                {
                    "$match":
                    {         
                        'mac':service['mac'],
                        'chipset':service['chipset']
                    }
                }
        ]))

        total = 0
        for data in datas:
            total += data['size']

        last_update_date = datas[-1]["_id"].generation_time.strftime("%a - %d %b %Y %H:%M:%S")
        service['last-update-data'] = last_update_date
        del service['_id']

        service['size'] = total

    return responses


api = Blueprint('api', __name__)


@api.route('/', methods=['GET'])
def index():
    return 'DIMS has been started'


@api.route('/client', methods=['POST'])
def client_register():
    client = request.get_json() if request.is_json else request.form.to_dict()
    if not JsonValidation().client_validation(client):
        abort(400)
    try:
        g.db.client_collection.update_one(client, {'$set': client},
                                          upsert=True)
    except errors.WriteError:
        return jsonify({'code': 500, 'message': 'Internal Server Error'}), 500
    return jsonify({'code': 200, 'message': 'Success'}), 200


@api.route('/service', methods=['POST'])
def service_register():
    service = request.get_json() if request.is_json else request.form.to_dict()
    if not JsonValidation().service_validation(service):
        abort(400)

    if not g.db.client_collection.find_one({'chipset': service['chipset'],
                                            'mac': service['mac']}):
        abort(422, {'message': 'Client not found',
                    'details': 'The client passed in service body could '
                    'not be found. Check the chipset and mac values.'})
    try:
        g.db.service_collection.update_one(service, {'$set': service},
                                           upsert=True)
    except errors.WriteError:
        return jsonify({'code': 500, 'message': 'Internal Server Error'}), 500
    return jsonify({'code': 200, 'message': 'Success'}), 200


@api.route('/data', methods=['POST'])
def data_register():
    data = request.get_json() if request.is_json else request.form.to_dict()
    if not JsonValidation().data_validation(data):
        abort(400)

    if 'counter' in data:
        if data['counter'] == -1:
            LogReport().end_report()
        logging.getLogger('dims').debug(f'"{data}"',
                                        extra={'size': sys.getsizeof(data)})

    client = g.db.client_collection.find_one({'chipset': data['chipset'],
                                              'mac': data['mac']})
    service = g.db.service_collection.find_one({'chipset': data['chipset'],
                                                'mac': data['mac'], 'number':
                                                data['serviceNumber']})

    if not (client and service):
        abort(422, {'message': 'Client or Service not found',
                    'details': 'The client or service passed in data body '
                    'could not be found. Check the chipset, mac and '
                    'serviceNumber values.'})

    data_size = sys.getsizeof(data)

    data['size'] = int(data_size)
    data['type'] = 'uncompressed'
    data['time_insert'] = float(datetime.datetime.now().timestamp())
    last_inserted_data = list(g.db.data_collection.find().sort([('_id',-1)]).limit(1))
    if len(last_inserted_data) != 0:
        data['time_diff'] = float(data['time_insert'])-float(last_inserted_data[0]['time_insert'])
    else:
        data['time_diff'] = 0
    try:
        g.db.data_collection.insert_one(data)
    except errors.WriteError:
        return jsonify({'code': 500, 'message': 'Internal Server Error'}), 500
    return jsonify({'code': 200, 'message': 'Success'}), 200


@api.route('/list/client', methods=['GET'])
def client_list():
    amount = request.args.get('latest', default=0, type=int)

    response = list(g.db.client_collection.find(ArgsValidation().client_args(
                                                request.args)).sort(
                                                "$natural", -1).limit(amount))

    for document in response:
        del document['_id']

    return jsonify(response), 200

# --------------- Seção de listagem de clientes contendo mais informações como last-update-time and number of services---------------#
@api.route('/list/client_full', methods=['GET'])
def client_list_full():
    amount = request.args.get('latest', default=0, type=int)
    pipeline = [
        
        { '$lookup':
                    {
                        'from' : 'datas',
                        'localField' : 'chipset',
                        'foreignField' : 'chipset',
                        'as' : 'data-aggregation'
                    }
        }
    ]
    table_agregation = list(g.db.client_collection.aggregate(pipeline))

    for document in table_agregation:
        last_update_date = ""
        if(document["data-aggregation"] != []):
            last_update_date = document["data-aggregation"][-1]["_id"].generation_time.strftime("%d/%m/%y %H:%M:%S")
        
        count_services = g.db.service_collection.count({"mac": document["mac"], "chipset": document["chipset"]})
        document['last-update-data'] = last_update_date
        document['number-of-services'] = count_services
        del document['_id']
        del document['data-aggregation']
        

    return jsonify(table_agregation), 200
# ----------------- Finalização de listagem contendo mais informações----------------- #

# --------------- Seção de criação de regras provisório ---------------# 
@api.route('/list/service')
def service_list():
    amount = request.args.get('latest', default=0, type=int)

    response = service_aggregate()

    return jsonify(response), 200


@api.route('/list/data')
def data_list():
    amount = request.args.get('latest', default=0, type=int)

    response = list(g.db.data_collection.find(ArgsValidation().data_args(
                                              request.args)).sort(
                                              "$natural", -1).limit(amount))


    for document in response:
        del document['_id']

    return jsonify(response), 200


@api.route('/report', methods=['GET'])
def report_data():
    LogReport().init_report_config()
    return jsonify({'code': 200, 'message': 'Success'}), 200


# --------------- Seção de criação de regras provisório ---------------#

@api.route("/rule", methods=['POST'])
def insert_rule():
    rule = request.get_json() if request.is_json else request.form.to_dict()

    try:
        g.db.rule_collection.insert_one(rule)
    except errors.WriteError:
        return jsonify({'code': 500, 'message': 'Internal Server Error'}), 500
    return jsonify({'code': 200, 'message': 'Success'}), 200

@api.route('/list/rule', methods=['GET'])
def list_rule():

    try:
        response = list(g.db.rule_collection.find(ArgsValidation.rule_args(
                                                   request.args )))
    except errors.WriteError:
        return jsonify({'code': 500, 'message': 'Internal Server Error'}), 500

    for document in response:
        del document['_id']

    return jsonify(response), 200

# ----------------- Finalização de criação de regras ----------------- #



# ----------------- List Interfaces (API para tela inicial de todos os projetos / gateway local) --------------------- #

@api.route('/list/interface', methods=['GET'])
def list_interface():
    try:
        # -------------- Contagem de quantidade de clientes ----------------- #

        channel_list = ['HTTP','ZIGBEE','TCP','UDP']
        list_response = []
        # Aggregation que calcula a quantidade de clientes que usam os protocolos especificados na lista channel_list
        for channel in channel_list: 
            json_reponse = {}
            json_reponse["name"] = channel
            json_reponse["clients"] = 0
            json_reponse["services"] = 0
            json_reponse["data_count"] = 0
            pipeline_clients_services = [
                {
                
                    '$match':
                    {
                        'channel':channel
                    }
                }
                ,
                {
                    '$count':"count"
                }
            ]

            pipeline_data = [
                {
                    '$match':
                    {
                        'channel':channel
                    }
                },
                {
                    '$group':
                    {
                        '_id':'$channel',
                        'channel_bytes_sum':{'$sum':'$size'}
                    }
                }
            ]

            client_list = list(g.db.client_collection.aggregate(pipeline_clients_services))
            if len(client_list) != 0:
                temp_channel = channel.lower()+"_clients"
                json_reponse["clients"] = client_list[0]['count']

        # Aggregation que calcula a quantidade de serviços por mecanismo de comunição utilizado na lista lista
            service_list = list(g.db.service_collection.aggregate(pipeline_clients_services))
            if len(service_list) != 0:
                temp_channel = channel.lower()+"_service"
                json_reponse["services"] = service_list[0]['count']


        # Aggregation que calcula a quantidade de dados que usam o mecanismo de comunicação utilizado na lista
            data_list = list(g.db.data_collection.aggregate(pipeline_data))
            if len(data_list) != 0:
                temp_channel = channel.lower()+"_data"
                json_reponse["data_count"] = data_list[0]['channel_bytes_sum']
            
            list_response.append(json_reponse)
    
    except errors.WriteError:
        return jsonify({'code': 500, 'message': 'Internal Server Error'}), 500

    return jsonify(list_response), 200


# ---------------------------- Fim do list interface ----------------------------- #


# --------------------------- List Gateway (listar informações acerca de gateways ) -------------------------- #

@api.route('/list/gateway',methods=['GET'])
def list_gateway():
    # Inserir a coleta dos dados associados ao gateway por meio da API que a Daiane está fazendo

    # Realiza a contagem de clientes/serviços/rules
    client_count = g.db.client_collection.count()
    service_count = g.db.service_collection.count()
    rule_count = g.db.rule_collection.count()

    time_now = ObjectId.from_datetime(datetime.datetime.now()+datetime.timedelta(minutes=180))
    time_now_minus_5 = ObjectId.from_datetime(datetime.datetime.now()+datetime.timedelta(minutes=180)-datetime.timedelta(minutes=5))

    compressed_data_count = list(g.db.data_collection.aggregate([
        {
            "$match":
            {
                'type':'compressed',
                 '_id':{'$gt':time_now_minus_5}
            }
        }
        ,
        {
           '$group':
           {
               '_id':'$type',
               'count':{'$sum':1},
               'sum_size_compressed':{'$sum':'$size_compressed'},
               'sum_size_document':{'$sum':'$size'}
           }
        }

        ]))

    # Aggregate que soma o tamanho dos tipos compressed e uncompressed e retorna em chaves de nome diferente
    rate_sum = list(g.db.data_collection.aggregate([
        {
            "$match":
            {
                '_id':{'$gt':time_now_minus_5}
            }
        }
        ,
        {
            '$project':
            {
                '_id':'compressed',
                'compressed_sum':{
                    '$cond':{'if':{'$eq':['$type','compressed']},'then':{'$sum':'$size_compressed'},'else':{'$sum':0}}
                },
                'uncompressed_sum':{
                    '$cond':{'if':{'$eq':['$type','uncompressed']},'then':{'$sum':'$size'},'else':{'$sum':0}}
                }
            }
        }
        ,
        {
           '$group':
           {
               '_id':'compressed',
               'compressed_sum':{'$sum':'$compressed_sum'},
               'uncompressed_sum':{'$sum':'$uncompressed_sum'}
           }
        }
        ]))


    # Aggregate que pega o documento mais recente da data_collection
    collections = [g.db.data_collection, g.db.service_collection, g.db.client_collection]
    time_dict = {}
    for collection in collections:
        latest_time = list(collection.aggregate([
            {
                '$sort':{'_id': -1}
            },
            { 
                '$limit': 1 
            }
            ,
            {
                '$project':{
                    '_id':'$_id'
                }
            }
        ]))
        #print(latest_time[0]['_id'].generation_time)
        #print(latest_time[0]['_id'])
        if len(latest_time) != 0:
            iso_timestamp = latest_time[0]['_id'].generation_time
            time_value = time.mktime(iso_timestamp.timetuple())
            if(collection == g.db.data_collection):
                time_dict['data'] = time_value
                time_dict['data_utc'] = iso_timestamp
            elif(collection == g.db.service_collection):
                time_dict['service'] = time_value
                time_dict['service_utc'] = iso_timestamp
            elif(collection == g.db.client_collection):
                time_dict['client'] = time_value
                time_dict['client_utc'] = iso_timestamp
        else:
            time_dict['data'] = 0
            time_dict['service'] = 0
            time_dict['client'] = 0
    
    if time_dict['data'] == 0 and time_dict['service'] == 0 and time_dict['client'] == 0:
        final_time = time_dict['data_utc']

    type_list = ['client','service','data']
    biggest_time = 0
    biggest_time_utc = ""
    for typeof in type_list:
        if (time_dict[typeof] > biggest_time):
            biggest_time = time_dict[typeof]
            biggest_time_utc = time_dict[typeof+"_utc"]

    if len(rate_sum) != 0:
        compressed_sum = rate_sum[0]['compressed_sum']
        uncompressed_sum = rate_sum[0]['uncompressed_sum']

        compressed_rate = compressed_sum/300
        uncompressed_rate = uncompressed_sum/300
    else:
        compressed_rate = 0
        uncompressed_rate = 0



    if len(compressed_data_count) != 0:
        # Dados sobre o batch de dados enviados, compactados ou não
        count = int(compressed_data_count[0]['count'])
        sum_size_compressed = int(compressed_data_count[0]['sum_size_compressed'])
        sum_size_document = int(compressed_data_count[0]['sum_size_document'])

        # Calculando o percentual de utilização do batch size
        compression_rate = (sum_size_compressed/sum_size_document)
        percent = (1-compression_rate)*100
    else:
        percent = 0

    response = {
            'percent':round(percent,2),
            'client_count':client_count,
            'service_count':service_count,
            'rule_count':rule_count,
            'compacted_rate':round(compressed_rate,2),
            'not_compacted_rate':round(uncompressed_rate,2),
            'last_updated':biggest_time_utc,
            'gateway_name':0,
            'gateway_master':0
    }
    response_list = []
    response_list.append(response)

    return jsonify(response_list),200



# ----------------------------- Fim de list gateway ---------------------------------- #

# --------------------------- List service-cloud (listar informações acerca de service-cloud ) -------------------------- #

@api.route('/list/service-cloud', methods=['GET'])
def service_cloud():

    # Pega todos os clientes existentes na collection
    amount = request.args.get('latest', default=0, type=int)
    clients = list(g.db.client_collection.find(ArgsValidation().client_args(
                                                request.args)).sort(
                                                "$natural", -1).limit(amount))

    service_list = service_aggregate()
    
    response_list = []
    for client in clients:

        for service in service_list:

            response_json = {
                'device_name':'None',
                'service_name':'None',
                'value':0,
                'associate_rules':0,
                'data_amount':0,
                'critical_messages':0,
                'storage_time':0,
                'last_updated':'None'
            }

            if(service['mac'] == client['mac'] and service['chipset'] == client['chipset']):
                
                ## Aggregate para pegar todas as mensagens críticas associadas a um determinado serviço
                data_list = list(g.db.data_collection.aggregate([
                {
                    "$match":
                    {         
                        'sensitive':'1',
                        'chipset':service['chipset'],
                        'mac':service['mac']
                    }
                }
                ]))

                ## Aggregate para pegar todas as mensagens associadas as um determinado serviço
                data_listed = list(g.db.data_collection.aggregate([
                {
                    "$match":
                    {         
                        'chipset':service['chipset'],
                        'mac':service['mac']
                    }
                }
                ]))

                ## Aggregate para pegar todas as regras associadas a um determinado serviço
                rule_response = list(g.db.rule_collection.aggregate([
                {
                    "$match":
                    {         
                        'chipset':service['chipset'],
                        'mac':service['mac']
                    }
                }
                ,
                {
                    "$project":
                    {
                        "_id":"rule",
                        "count":{"$sum":1}
                    }
                }
                ]))
                
                # Coloca os valores adquiridos no dicionário response_json
                response_json['device_name'] = client['name']
                response_json['service_name'] = service['name']
                if len(rule_response) != 0:
                    response_json['associate_rules'] = rule_response[0]['count']
                response_json['data_amount'] = service['size']
                response_json['critical_messages'] = len(data_list)
                response_json['last_updated'] = service['last-update-data']
                try:
                    response_json['value'] = str(data_listed[-1]['value'][-1])
                except IndexError:
                    response_json['value'] = 'None'
                    
                # Coloca o dicionário na lista final de resposta
                response_list.append(response_json)

    return jsonify(response_list),200
            
# -------------------- Fim do list service-cloud -------------------- #


# ------------------- Listagem service-cloud-interface ---------------- #
@api.route('/list/service-cloud-interface',methods=['GET'])
def service_cloud_interface():

    # Pega todos os clientes existentes na collection
    amount = request.args.get('latest', default=0, type=int)
    clients = list(g.db.client_collection.find(ArgsValidation().client_args(
                                                request.args)).sort(
                                                "$natural", -1).limit(amount))

    
    response_list = []
    for client in clients:

        ## JSON que mostra o formato da resposta do método da API
        response_json = {
            'device_name':'None',
            'device_interface':'None',
            'device_identifier':0,
            'service_count':0,
            'last_updated':'None',
            'register_expiration':'None'
        }

        ## Aggregate que pega todos os dados associados ao cliente da iteração atual
        data_response = list(g.db.data_collection.aggregate([
                {
                    "$match":
                    {         
                        'chipset':client['chipset'],
                        'mac':client['mac']
                    }
                }
        ]))
        ## Pega o último elemento da lista retornada e coloca em last_data_update o horário em que
        ## o documento foi inserido
        if(len(data_response) != 0):
            last_data_update = data_response[-1]['_id'].generation_time.strftime("%a - %d %b %Y %H:%M:%S")
        service_count = g.db.service_collection.count()
        response_json['device_name'] = client['name']
        response_json['device_interface'] = client['channel']
        response_json['device_identifier'] = client['mac']
        response_json['service_count'] = service_count
        response_json['last_updated'] = last_data_update

        response_list.append(response_json)
    
    return jsonify(response_list),200

# ------------------- FIM Listagem service-cloud-interface ---------------- #

# ------------------- Listagem service-cloud-average ------------------------- #
@api.route('/list/service-cloud-average',methods=['GET'])
def service_cloud_average():
        
    # Pega todos os clientes existentes na collection
    amount = request.args.get('latest', default=0, type=int)
    clients = list(g.db.client_collection.find(ArgsValidation().client_args(
                                                request.args)).sort(
                                                "$natural", -1).limit(amount))

    service_list = service_aggregate()

    result_list = []
    for client in clients:

        for service in service_list:

            # JSON que contem o formato da resposta do método
            response_json = {
                'device_name':'None',
                'service_name':'None',
                'input_average':0,
                'last_updated':'None'
            }

            # Aggregate que pega todos os dados associados a um serviço e calcula a média de time_diff
            data_time_average = list(g.db.data_collection.aggregate([
                {
                    "$match":
                    {         
                        'serviceNumber':service['number']
                    }
                }
                ,
                {
                    "$group":
                    {
                        '_id':'average',
                        'average_input_time':{'$avg':'$time_diff'}
                    }
                }
            ]))


            if(service['mac'] == client['mac'] and service['chipset'] == client['chipset']):
                response_json['device_name'] = client['name']
                response_json['service_name'] = service['name']
                response_json['last_updated'] = service['last-update-data']
                if len(data_time_average) != 0:
                    response_json['input_average'] = data_time_average[0]['average_input_time']

                result_list.append(response_json)

    return jsonify(result_list),200

# ---------------------------------------- Método de inserção de dados enviados --------------------- #
@api.route('/telemetry',methods=['POST'])
def send_data_telemetry():
    telemetry_dict = request.get_json() if request.is_json else request.form.to_dict()

    try:
        g.db.telemetry_collection.insert_one(telemetry_dict)
    except errors.WriteError:
        return jsonify({'code': 500, 'message': 'Internal Server Error'}), 500
    return jsonify({'code': 200, 'message': 'Success'}), 200

# --------------------------------- FIM do método de inserção de dados enviados ----------------------- #


# ---------------------------------------- Método de inserção de dados enviados --------------------- #
@api.route('/telemetry-gateway',methods=['POST'])
def send_data_telemetry_gateway():
    telemetry_dict = request.get_json() if request.is_json else request.form.to_dict()
    gateway = list(g.db.telemetry_collection.find_one({'remote_gateway_name': telemetry_dict['remote_gateway_name']}))  if g.db.telemetry_collection.find_one({'remote_gateway_name': telemetry_dict['remote_gateway_name']}) != None else [] 
    if len(gateway) != 0:
        try:
            g.db.telemetry_collection.insert_one(telemetry_dict)
        except errors.WriteError:
            return jsonify({'code': 500, 'message': 'Internal Server Error'}), 500
        return jsonify({'code': 200, 'message': 'Success'}), 200
    else:
        return jsonify({'code':400,'message':'remote-gateway already exists'}),400

# --------------------------------- FIM do método de inserção de dados enviados ----------------------- #

@api.route('/list/gateway-cloud',methods=['GET'])
def list_gateway_cloud():

    # Gera o ObjectID de agora e 5 minutos atrás
    time_now = ObjectId.from_datetime(datetime.datetime.now()+datetime.timedelta(minutes=180))
    time_now_minus_5 = ObjectId.from_datetime(datetime.datetime.now()+datetime.timedelta(minutes=180)-datetime.timedelta(minutes=5))

    # Pega todos os remote gateways cadastrados em telemetry_collection
    remote_gateways = list(g.db.telemetry_collection.find({'remote_gateway_name':{'$exists':'true'}}))

    print("REMOTE GATEWAYS: {}".format(remote_gateways))

    response_list = []
    for remote_gateway in remote_gateways:

        response = {
            'remote_gateway':'None',
            'total_sent_compacted':0,
            'economy':0,
            'sensitive_transmission':0,
            'compacted_transmission':0
        }

        uncompressed_data = list(g.db.telemetry_collection.aggregate([
        {
            "$match":
            {
                'type':'uncompressed',
                 '_id':{'$gt':time_now_minus_5},
                 'remote_gateway':remote_gateway['remote_gateway_name']
            }
        }
        ,
        {
           '$group':
           {
               '_id':'$type',
               'count':{'$sum':1},
               'sum_size':{'$sum':'$sent_size'},
           }
        }

        ]))

        compressed_data = list(g.db.telemetry_collection.aggregate([
        {
            "$match":
            {
                'type':'compressed',
                 '_id':{'$gt':time_now_minus_5},
                 'remote_gateway':remote_gateway['remote_gateway_name']
            }
        }
        ,
        {
           '$group':
           {
               '_id':'$type',
               'count':{'$sum':1},
               'sum_size':{'$sum':'$sent_size'},
           }
        }
        ]))

        sensitive_transmission = list(g.db.telemetry_collection.aggregate([
        {
            "$match":
            {
                'senstive':1,
                 '_id':{'$gt':time_now_minus_5},
                 'remote_gateway':remote_gateway['remote_gateway_name']
            }
        }
        ,
        {
           '$group':
           {
               '_id':'$type',
               'count':{'$sum':1},
               'sum_size':{'$sum':'$sent_size'},
           }
        }
        ]))

        if len(compressed_data) != 0:
            response['compacted_transmission'] = compressed_data[0]['sum_size']/300
            response['total_sent_compacted'] = compressed_data[0]['sum_size']

        if len(sensitive_transmission) != 0:
            response['sensitive_transmission'] = sensitive_transmission[0]['sum_size']/300
        
        response['remote_gateway'] = remote_gateway['remote_gateway_name']

        response_list.append(response)

    return jsonify(response_list),200