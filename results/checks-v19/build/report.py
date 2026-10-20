"""Summarize the measured v19 gates without rerunning or changing their inputs."""

from __future__ import annotations

import importlib.metadata
import json
from pathlib import Path
import platform
import re
import sys
import xml.etree.ElementTree as ET

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from energy_mutants import MUTANTS
from verify import DAYS, LARGE, RENAMES, TASK, write


def read(path):
    return json.loads(path.read_text())


def mutations(path):
    result = {}
    for line in path.read_text().splitlines():
        match = re.match(r"(\S+)\s+(CAUGHT|MISSED)\s+(.*)", line)
        if not match:
            continue
        name, status, detail = match.groups()
        failures = {"test_" + m[0]: m[1].split(",") for m in
                    re.findall(r"(?:^|; )([a-z_]+):((?:visible|h[1-4])(?:,(?:visible|h[1-4]))*)(?=;|\s|$)", detail)}
        result[name] = {"caught": status == "CAUGHT", "failed": failures, "raw": line}
    return result


def main():
    canonical = read(OUT / "canonical-deliveries.json")
    matrix = read(OUT / "matrix.json")
    mutants = mutations(OUT / "canonical-mutants.log")
    assert set(mutants) == set(MUTANTS) and all(v["caught"] and v["failed"] for v in mutants.values())
    assert mutants["parts_by_name_prefix"]["failed"]["test_units_within_ratings_and_availability"] == ["h2", "h3", "h4"]
    assert read(OUT / "canonical-mutants.command.json")["returncode"] == 0
    write("mutants.json", mutants)
    table = ["# v19 mutation failures", "", "Each entry comes from the actual `tools/energy_mutants.py` run.", "",
             "| Mutant | Failed tests and days |", "|---|---|"]
    for name, value in mutants.items():
        table.append("| `" + name + "` | " + "; ".join(f"`{k}`: {', '.join(v)}" for k, v in value["failed"].items()) + " |")
    (OUT / "mutants.md").write_text("\n".join(table) + "\n")

    baseline_mutants = mutations(ROOT / "results/checks-v18/final-mutants.log")
    mutation_changes = {name: {"v18": baseline_mutants[name]["failed"], "v19": value["failed"]}
                        for name, value in mutants.items() if name in baseline_mutants
                        and baseline_mutants[name]["failed"] != value["failed"]}
    fresh = read(OUT / "fresh-summary.json")
    fresh_comparison = {}
    for seed in fresh:
        after = read(OUT / f"fresh-{seed}.manifest.json")
        before = read(ROOT / f"results/checks-v18/final-fresh-verified/seed-{seed}/manifest.json")
        before = json.loads(json.dumps(before).replace("GE1 LT radiator", "LT radiator 1").replace("GE2 LT radiator", "LT radiator 2"))
        names_equal = list(before["days"]) == list(after["days"])
        specs_equal = all(v["spec"] == before["days"][k]["spec"] for k, v in after["days"].items())
        max_delta = max(abs(v["milp_cost_gbp"] - before["days"][k]["milp_cost_gbp"]) for k, v in after["days"].items())
        assert names_equal and specs_equal and max_delta < 1e-8
        fresh_comparison[seed] = {"same_accepted_draws": names_equal, "specs_identical_after_rename": specs_equal,
                                  "max_abs_milp_difference_gbp": max_delta}
    v18_scores = {p.parent.parent.name: read(p)["results"]["summary"]["passed"] for p in
                  (ROOT / "results/v18-trials").glob("*/verifier/ctrf.json")}
    changed_scores = {name: {"v18": old, "v19": canonical[name]["passed_tests"]}
                      for name, old in v18_scores.items() if old != canonical[name]["passed_tests"]}
    comparison = {"mutant_failed_test_sets_changed": mutation_changes,
                  "added_mutants": sorted(set(mutants) - baseline_mutants.keys()),
                  "fresh": fresh_comparison, "v18_trial_scores": v18_scores,
                  "v18_trial_scores_changed": changed_scores}
    write("v18-comparison.json", comparison)

    from reference import Day
    violations = {}
    for name in canonical:
        rows = []
        for day_name in DAYS:
            plan_path = LARGE / f"matrix/{name}/{day_name}.json"
            if not plan_path.is_file() or any(k.startswith("execution_") for k in matrix[name]["days"][day_name]["failures"]):
                continue
            plan = read(plan_path)
            day = Day(TASK / f"tests/days/{day_name}")
            for t, p in enumerate(plan["periods"]):
                for group in ("engines_kwe", "boilers_kw", "chillers_kw"):
                    for unit, kw in p[group].items():
                        if kw > .5 and not day.available[unit][t]:
                            touching = [o for o in day.status["outages"] if int(o["from"][:2]) * 60 + int(o["from"][3:]) < day.clock[t] + 30
                                        and int(o["to"][:2]) * 60 + int(o["to"][3:]) > day.clock[t]]
                            rows.append({"day": day_name, "start": p["start"], "unit": unit, "output_kw": kw,
                                         "outages_touching_period": touching})
        violations[name] = rows
    write("availability-violations.json", violations)
    junit = ET.parse(LARGE / "oracle-junit.xml").getroot()
    cases = list(junit.iter("testcase"))
    assert len(cases) == 55 and all(c.find("failure") is None and c.find("error") is None for c in cases)
    costs = {name: {k: v[k] for k in ("cost_gbp", "milp_gbp", "delta_gbp")}
             for name, v in matrix["oracle"]["days"].items()}
    write("oracle-costs.json", costs)
    gates = {"A_prime": read(OUT / "A-prime.json")["passed"],
             "B_55_tests": len(cases) == 55 and read(OUT / "canonical-eval.command.json")["returncode"] == 0,
             "B_cost_delta_below_0.001_gbp": all(abs(v["delta_gbp"]) < .001 for v in costs.values()),
             "B_fresh_48_days": len(fresh) == 3 and all(v["accepted_days"] == 16 and all(not(r["failed"] or r["errors"])
                       for r in v["results"].values()) for v in fresh.values()),
             "C_42_mutants": len(mutants) == 42 and all(v["caught"] for v in mutants.values()),
             "F_six_v18_deliveries_fail": len(v18_scores) == 6 and all(canonical[n]["failed"] for n in v18_scores)}
    assert all(gates.values()), gates
    write("gates.json", gates)
    write("runtime.json", {"python": platform.python_version(), "executable": sys.executable,
          **{p: importlib.metadata.version(p) for p in ("numpy", "scipy", "pytest")}})

    lines = ["# v19 build 验收", "", "结果：A′、B、C、F 全部通过；四份指定对照均已实际运行。未运行 Harbor、Docker。",
             "分支 `v19`，基线 `f02497a`；未提交、推送、切分支或修改历史。", "",
             "## 命令与产物", "", "所有仓库工具均使用以下 Python 和三个环境变量：", "", "```sh",
             f"PY={sys.executable}", f"D={LARGE}", "export PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1",
             '"$PY" results/checks-v19/build/verify.py snapshot',
             '"$PY" tools/build_energy_days.py',
             '"$PY" results/checks-v19/build/verify.py static',
             '"$PY" results/checks-v19/build/verify.py canonical',
             '"$PY" results/checks-v19/build/verify.py matrix',
             '"$PY" results/checks-v19/build/verify.py deliveries',
             '"$PY" results/checks-v19/build/verify.py mutants',
             'for S in 2026 2403 87123; do',
             '  "$PY" tools/fresh_days.py --days 16 --seed "$S" --output "$D/fresh-$S" tasks/energy-centre-dispatch/solution/app',
             'done',
             '"$PY" results/checks-v19/build/verify.py fresh-summary',
             'PLANS_DIR="$D/matrix/oracle" "$PY" -m pytest -q -p no:cacheprovider --junitxml="$D/oracle-junit.xml" tasks/energy-centre-dispatch/tests/test_plans.py',
             '"$PY" results/checks-v19/build/report.py', "git diff --check", "git status --porcelain --untracked-files=all",
             "git diff -- tasks/energy-centre-dispatch/instruction.md tasks/energy-centre-dispatch/environment/planner tasks/energy-centre-dispatch/environment/dispatch.py",
             '"$PY" results/checks-v19/build/verify.py integrity',
             "```", "", "`canonical` 与 `mutants` 分别调用未改动的原 CLI；实际子命令、退出码、耗时及环境变量见对应 `*.command.json`。",
             "`matrix` 用现有 `check_v18.check_app` 保存每份计划、两次执行日志、物理重算及逐项断言；`deliveries` 再经原 `eval_energy.evaluate` 对全部旧交付物跑完整 pytest。",
             "fresh 的完整命令见三个 `fresh-*.command.json`；上面列出等价循环。输出目录须为新目录，复现时另选 `<D>`，或先保留原证据再调整 `verify.py` 的 `LARGE`。",
             "完整计划、随机日输入、原始 JUnit、v18 基线快照在 `<D>`；仓库保留摘要、manifest、日志和可复现脚本。", "",
             "## A′ 与数据生成", "", "通过：除 `environment/data/plant.json` 外，可见文件与 v8.1 逐字节相同；文件集合也相同。",
             "plant 唯一差异是两处名称，见 [plant-v8.1.diff](plant-v8.1.diff)。五天 plant 完全相同，visible 与 environment/data 逐字节相同。",
             "各天相对 `f02497a` 的输入仅做任务书要求的名称替换，时间和其他数据未变。证据：[A-prime.json](A-prime.json)、[baseline-snapshot.json](baseline-snapshot.json)。", "",
             "## B 标准答案和参考模型", "", "原 CLI 退出 0；实际 pytest **55/55**，见 [canonical-eval.log](canonical-eval.log)、[oracle-pytest.log](oracle-pytest.log)。", "",
             "| Day | MILP £ | true_flows £ | 差额 £ |", "|---|---:|---:|---:|"]
    for name in DAYS:
        v = costs[name]
        lines.append(f"| {name} | {v['milp_gbp']:.12f} | {v['cost_gbp']:.12f} | {v['delta_gbp']:+.12f} |")
    lines += ["", "五天最大绝对差额均 < £0.001，见 [oracle-costs.json](oracle-costs.json)。",
              "v18/v19 五天所有原有设备可用性、其他模型属性、MILP 完整结果、标准答案完整计划、true_flows 全部相同；新增接受的热路名称仅 `hospital buildings`。",
              "证据：[v18-invariance.json](v18-invariance.json)。定向探针还把热路键改名、出口改成两个无机组前缀的任意名字，分别检修两个出口；参考和答案都只停 GE1，见 [topology-probe.json](topology-probe.json)。", "",
              "| Seed | 接受/抽取 | radiator 1 检修数 | radiator 2 检修数 | 结果 |", "|---|---:|---:|---:|---|"]
    for seed, value in fresh.items():
        lines.append(f"| {seed} | {value['accepted_days']}/{value['draws']} | {value['radiator_outages']['LT radiator 1']} | {value['radiator_outages']['LT radiator 2']} | 16/16 通过，原 CLI 退出 0 |")
    lines += ["", "证据：[fresh-summary.json](fresh-summary.json)、三个 `fresh-*.log`、`fresh-*.manifest.json` 与 `fresh-*.command.json`。",
              "汇总脚本最初额外断言每个 seed 都覆盖两个名字，在 87123 上失败（两种检修数为 0/4）；当时三条 fresh 原命令均已退出 0。已将汇总断言改为三组总体覆盖，不改采样、不重新抽取或重跑；原失败保留于 `fresh-runner.log`，最终汇总退出 0，见 `fresh-summary-runner.log`。", "",
              "## C 变异", "", "**42/42 被抓，原 CLI 退出 0**，包含原 41 个和 `parts_by_name_prefix`。",
              "新增变异只凭机组名前缀归属部件，实际在 **h2、h3、h4 的 `test_units_within_ratings_and_availability`** 失败。",
              "全部变异各自失败的测试和日期列于 [mutants.md](mutants.md)；结构化结果见 [mutants.json](mutants.json)，原始运行见 [canonical-mutants.log](canonical-mutants.log)、[canonical-mutants.command.json](canonical-mutants.command.json)。",
              "执行错误、超时变异按原工具规则判无有效计划；未把它们描述成物理约束失败。", "",
              "## F 六份 v18 交付物", "", "全部失败；下表为原 pytest 结果。`availability` 指 `test_units_within_ratings_and_availability`。", "",
              "| 交付物 | v19 通过项 | 失败情况 |", "|---|---:|---|"]
    reasons = {
        "ecd18-run1-claude": "availability: h1/h2/h4；least_cost: h3，实际成本超过 MILP £1231.611769",
        "ecd18-run1-codex": "availability: h1/h2/h3/h4",
        "ecd18-run2-claude": "五天两次均 exit 1；硬编码要求 `GE1 LT radiator`，实际得到 `LT radiator 1`，全部 55 项失败",
        "ecd18-run2-codex": "四个隐藏日两次均 exit 1：h1/h2/h4 在 00:00、h3 在 13:30 报 `no feasible loading`，隐藏日全部测试失败",
        "ecd18-run3-claude": "availability: h1/h2/h3/h4",
        "ecd18-run3-codex": "availability: h1/h2/h3/h4"}
    for name in sorted(v18_scores):
        lines.append(f"| {name} | {canonical[name]['passed_tests']}/55 | {reasons[name]} |")
    lines += ["", "原 CLI 的逐测试/逐日失败和错误：[canonical-deliveries.json](canonical-deliveries.json)、[deliveries-runner.log](deliveries-runner.log)。",
              "计划逐时段检修冲突：[availability-violations.json](availability-violations.json)。完整回溯、计划、两次运行耗时见 [matrix.json](matrix.json) 和 `<D>/matrix/`。", "",
              "## 四份对照（仅记录）", "", "| 交付物 | v19 结果 | 原因 |", "|---|---|---|"]
    contrast = ["ecd16-run2-claude", "ecd17-run2-claude-parts", "ecd17-run2-codex-parts", "ecd18-run2-claude"]
    for name in contrast:
        cause = "从热路处理散热器及其可用性，未出现失败" if name != "ecd18-run2-claude" else "在建模前强制校验旧散热器名，五天均报 ValueError；这次失败发生在名称校验阶段"
        lines.append(f"| {name} | {canonical[name]['passed_tests']}/55 | {cause} |")
    lines += ["", "三个较早的强对照仍全部通过；不能把改名说成已击败这三份程序。证据同 `canonical-deliveries.json`、`matrix.json` 及归档源码。", "",
              "## 与 v18 不一致的结果", "", "- 可见 plant 的两个名称改变，因此 A 改为任务书定义的 A′；其余可见文件保持相同。",
              "- C 从 41/41 增至 42/42；原 41 个的失败测试/日期集合变化见下项。",
              f"- 原变异失败集合变化：`{json.dumps(mutation_changes, ensure_ascii=False)}`。对照来源为已有 `results/checks-v18/final-mutants.log`，未在本轮重跑旧变异。",
              f"- 六份 v18 交付物的通过数变化：`{json.dumps(changed_scores, ensure_ascii=False)}`；其余五份通过数与已有 v18 CTRF 记录一致。",
              "- 三个较早的强对照仍为 55/55，与已有 `results/checks-v18/canonical_eval.json` 一致。",
              "- B 五天成本和参考/答案计划未变。fresh 接受的抽样编号和规格（名称归一后）与 v18 完全相同；MILP 成本最大浮点差见 `v18-comparison.json`，均 < £1e-8，48 天通过结论相同。",
              "- v18 旧日志的执行超时等原始错误文本未要求一致，也未当成本轮 v18 重跑结果。", "",
              "## 修改范围与遗留", "", "仅修改生成器、参考模型、标准答案、变异和 fresh 工具、生成数据及本目录；`test_plans.py` 未改。",
              "参考和标准答案均由包含 `<engine> intercooler` 的热路 `to` 列表推出散热器依赖，不硬编码新名字。其他中冷器、HT 源、冷凝器和 AC1 部件处理保持原样。",
              "未运行 Harbor/Docker；按任务书留给 Claude。未删除用户文件，未安装依赖，未更改全局或网络设置。",
              "`tools/`、当前 task 和本验收目录没有 `__pycache__`。历史 `jobs/` 中已有 45 个 pyc，mtime 均早于本次 v18 快照；遵守不删用户文件的限制予以保留，见 `existing-caches.json`，不能宣称整个仓库原本没有缓存。",
              "验收汇总见 [gates.json](gates.json)；最终 Git 范围、禁止修改项和无缓存检查见 `final-integrity.json`、`final-checks.log`。"]
    (OUT / "README.md").write_text("\n".join(lines) + "\n")
    print(json.dumps(gates, indent=2))


if __name__ == "__main__":
    main()
