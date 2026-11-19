"""Hold an image build under batch-probe's ThermalController (https://github.com/ahb-sjsu/batch-probe).

A docker build cannot change its thread count mid-run, so this pauses the build's containers while the controller
recommends fewer than half the build's CPUs, and unpauses them once it allows three quarters again. The build's
containers are the running ones that did not exist when the build started.

Usage: python3 thermal_pause.py <file of container IDs present before the build> <stop file> [build CPUs, default 12]
"""
import subprocess
import sys
import time

from batch_probe import ThermalController


def docker(*args):
    return subprocess.run(["docker", *args], capture_output=True, text=True, check=False).stdout.split()


def main(before_file, stop_file, max_threads=12):
    pause_below, resume_at = max_threads // 2, (3 * max_threads) // 4
    with open(before_file, encoding="utf-8") as fh:
        before = set(fh.read().split())
    ctrl = ThermalController(target_temp=78.0, max_threads=max_threads, min_threads=1, verbose=False)
    ctrl.start()
    paused = set()
    last_log = 0.0
    try:
        while True:
            try:
                open(stop_file).close()
                break
            except FileNotFoundError:
                pass
            n = ctrl.get_threads()
            mine = set(docker("ps", "-q", "--no-trunc")) - before
            if n < pause_below:
                for c in sorted(mine - paused):
                    docker("pause", c)
                    paused.add(c)
            elif n >= resume_at and paused:
                for c in sorted(paused):
                    docker("unpause", c)
                paused.clear()
            if time.time() - last_log >= 60:
                print(f"{time.strftime('%H:%M:%S')} temp {ctrl.kf.temp:.1f} C threads {n} "
                      f"build containers {len(mine)} paused {len(paused)}", flush=True)
                last_log = time.time()
            time.sleep(5)
    finally:
        for c in sorted(paused):
            docker("unpause", c)
        ctrl.stop()
        s = ctrl.summary()
        print(f"done: temp max {s.get('temp_max', float('nan')):.1f} C, mean {s.get('temp_mean', float('nan')):.1f} C",
              flush=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 12)
