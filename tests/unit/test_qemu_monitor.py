"""Slow screenshot writes and monitor errors must not become misleading UI failures."""
import importlib.util
from pathlib import Path
import socket
import threading
import time

import pytest

spec = importlib.util.spec_from_file_location('boot_monitor',
    Path(__file__).parents[1] / 'boot/boot-test.py')
boot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(boot)

@pytest.mark.parametrize('error', [False, True])
def test_monitor_waits_for_completion_and_reports_failure(tmp_path, error):
    path = str(tmp_path / 'monitor.sock')
    output = tmp_path / 'screenshot.ppm'
    with socket.socket(socket.AF_UNIX) as listener:
        listener.bind(path)
        listener.listen(1)
        def serve():
            connection, _ = listener.accept()
            with connection:
                connection.sendall(b'QEMU monitor\r\n(qemu) ')
                assert connection.recv(4096).startswith(b'screendump ')
                connection.sendall(b'working...\r\n')
                time.sleep(.05)
                if error:
                    connection.sendall(b'Error: permission denied\r\n(qemu) ')
                else:
                    output.write_bytes(b'completed screenshot')
                    connection.sendall(b'(qemu) ')
        thread = threading.Thread(target=serve)
        thread.start()
        try:
            if error:
                with pytest.raises(RuntimeError, match='permission denied'):
                    boot.monitor(path, f'screendump {output}')
            else:
                boot.monitor(path, f'screendump {output}')
                assert output.read_bytes() == b'completed screenshot'
        finally:
            thread.join(timeout=2)
