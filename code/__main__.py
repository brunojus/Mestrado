from dims import create_app
import subprocess
import socket
import click
import os

app = create_app()


@click.group(invoke_without_command=True)
@click.option('--root', is_flag=True,
              help='Flag that indicates if not is a root.')
@click.option('-p', '--peerport', type=int, default=5010, help='Peer port.')
@click.option('-r', '--rootport', type=int, default=5010, help='Root port.')
def start_server(root, peerport, rootport):
    # starts chord
    local_ip = socket.gethostbyname(socket.getfqdn()) 
    args = f'-m 1 -p {peerport} -h {local_ip}'.split(' ') if root else \
    f'-m 0 -p {peerport} -h {local_ip} -r {rootport} -R {local_ip}'.split(' ')
    argv = ['dht_peer', *args]
    subprocess.Popen(argv)

    # dims flask
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
    return True


if __name__ == '__main__':
    start_server()
