"""Sample process RSS/CPU and system pressure; no invented GPU-utilization metric."""
import os
import platform
import threading
from time import perf_counter
from store29 import digest

try:
    import psutil
except ImportError:
    psutil = None


def machine_identity():
    return {'system': platform.system(), 'machine': platform.machine(),
            'host_hash': digest(platform.node()), 'logical_cpus': os.cpu_count(),
            'ram_bytes': psutil.virtual_memory().total if psutil else None}


class ResourceSampler:
    def __init__(self, interval=.5):
        self.interval = interval
        self.samples = []
        self.stop_event = threading.Event()
        self.thread = None
        self.started = None
        self.error_count = 0

    def sample(self):
        if psutil is None:
            return
        try:
            vm, swap = psutil.virtual_memory(), psutil.swap_memory()
            processes = []
            denied = 0
            for proc in psutil.process_iter(['pid', 'name']):
                name = (proc.info['name'] or '').lower()
                if 'ollama' not in name:
                    continue
                try:
                    with proc.oneshot():
                        times = proc.cpu_times()
                        processes.append({'pid': proc.pid, 'name': proc.info['name'],
                                          'rss_bytes': proc.memory_info().rss,
                                          'cpu_seconds': times.user + times.system})
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    denied += 1
            self.samples.append({'elapsed_seconds': perf_counter() - self.started,
                                 'system_available_bytes': vm.available, 'swap_used_bytes': swap.used,
                                 'python_rss_bytes': psutil.Process().memory_info().rss,
                                 'ollama_processes': processes, 'unreadable_processes': denied})
        except (OSError, psutil.Error):
            self.error_count += 1

    def loop(self):
        while not self.stop_event.wait(self.interval):
            self.sample()

    def __enter__(self):
        self.started = perf_counter()
        self.sample()
        if psutil is not None:
            self.thread = threading.Thread(target=self.loop, daemon=True)
            self.thread.start()
        return self

    def __exit__(self, *args):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=2)
        self.sample()

    def result(self):
        spans = {}
        for sample in self.samples:
            for proc in sample['ollama_processes']:
                spans.setdefault(proc['pid'], []).append(proc)
        observed = [p for values in spans.values() for p in values]
        cpu_delta = sum(max(0, values[-1]['cpu_seconds'] - values[0]['cpu_seconds'])
                        for values in spans.values() if len(values) > 1)
        wall = self.samples[-1]['elapsed_seconds'] if self.samples else 0
        return {'available': psutil is not None, 'sample_interval_seconds': self.interval,
                'samples': self.samples, 'sampling_errors': self.error_count,
                'ollama_observed': bool(observed),
                'ollama_peak_summed_rss_bytes': max((sum(p['rss_bytes'] for p in s['ollama_processes'])
                                                   for s in self.samples), default=None) if observed else None,
                'ollama_observed_cpu_seconds': cpu_delta if observed else None,
                'ollama_average_cpu_percent': 100 * cpu_delta / wall if observed and wall else None,
                'system_min_available_bytes': min((s['system_available_bytes'] for s in self.samples), default=None),
                'swap_before_bytes': self.samples[0]['swap_used_bytes'] if self.samples else None,
                'swap_after_bytes': self.samples[-1]['swap_used_bytes'] if self.samples else None,
                'gpu_utilization_percent': None,
                'note': 'Sampled RSS sums can double-count shared mappings. Apple RAM/VRAM are shared; do not add RSS and size_vram. CPU can exceed 100%; short-lived processes may be missed.'}

