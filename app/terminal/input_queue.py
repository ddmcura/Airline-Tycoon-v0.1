"""Input-only worker. It never receives a session or simulation reference."""

from queue import Queue, Empty, Full
from threading import Event, Thread


class TerminalInput:
    def __init__(self, stream):
        self.stream = stream
        self.queue = Queue(maxsize=1)
        self.closed = Event()
        self.eof = False
        self.worker = Thread(target=self._read, daemon=True, name='terminal-input')
        self.worker.start()

    def _read(self):
        while not self.closed.is_set():
            try:
                value = self.stream.readline()
            except Exception as exc:
                value = exc
            # One outstanding line bounds memory even for pasted input.
            while not self.closed.is_set():
                try:
                    self.queue.put(value, timeout=.05)
                    break
                except Full:
                    pass
            if value == '' or isinstance(value, Exception):
                return

    def poll(self, timeout=0):
        if self.eof:
            return ''
        try:
            value = self.queue.get(timeout=timeout)
        except Empty:
            return None
        if isinstance(value, Exception):
            raise value
        if value == '':
            self.eof = True
        return value

    def close(self):
        self.closed.set()
