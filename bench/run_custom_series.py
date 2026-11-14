"""Start fresh threshold preparation and one six-cell comparison, without retries."""

import argparse
import os
from pathlib import Path

from prepare_custom_metric import main as prepare, now, save
from run_custom_comparison import main as compare, read
from run_lock import exclusive_main


@exclusive_main
def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    folder = args.output_dir.resolve()
    preparation, comparison = folder / "preparation-new", folder / "comparison-new"
    if not args.execute:
        print("Fresh preparation (targets 1, 2), then six CPU/request cells. No files or runtime changed.")
        return 0
    folder.mkdir(parents=True, exist_ok=False)
    state = dict(status="preparing", pid=os.getpid(), started_at=now(), errors=[],
                 preparation_dir=str(preparation), comparison_dir=str(comparison))
    save(folder / "workflow.json", state)
    try:
        if prepare(["--output-dir", str(preparation), "--execute"]):
            raise RuntimeError("Preparation stopped; see preparation-new/manifest.json")
        manifest = read(preparation / "manifest.json")
        if manifest.get("status") != "finished" or manifest.get("selected_target") != 1:
            raise ValueError("Fresh preparation did not select target 1; comparison not started")
        state.update(status="comparing", comparison_started_at=now())
        save(folder / "workflow.json", state)
        if compare(["--output-dir", str(comparison), "--preparation-dir", str(preparation), "--execute"]):
            raise RuntimeError("Comparison stopped; see comparison-new/manifest.json")
        manifest = read(comparison / "manifest.json")
        if manifest.get("status") != "finished" or len(manifest.get("completed", [])) != 6:
            raise ValueError("Comparison did not finish all six cells")
        state["status"] = "finished"
        return 0
    except (Exception, KeyboardInterrupt) as error:
        state.update(status="stopped", errors=[str(error)])
        print(str(error), flush=True)
        return 1
    finally:
        state["finished_at"] = now()
        save(folder / "workflow.json", state)


if __name__ == "__main__":
    raise SystemExit(main())
