import click
import evn
from evn.cli.click_util import *


def test_extract_command_info():

    def greet(count, name):
        """Greet someone a specified number of times."""
        for _ in range(count):
            click.echo(f'Hello, {name}!')

    arg = click.argument('name')(greet)
    opt = click.option('--count', default=1, help='Number of greetings.')(arg)
    cmd = click.command()(opt)

    info = extract_command_info(cmd)
    assert info.function == greet
    assert len(info['parameters']) == 2
    assert info['parameters'][0]['name'] == 'count'
    assert info['parameters'][1]['name'] == 'name'
