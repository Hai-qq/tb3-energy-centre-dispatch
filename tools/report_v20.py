"""Render compact review tables directly from retained v20 evidence."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/checks-v20"
DAYS = ["visible", "h1", "h2", "h3", "h4"]


def read(path):
    return json.loads(path.read_text()) if path.exists() else None


def main():
    report = ["# 固定五日与差分矩阵", "", "本文件由 `tools/report_v20.py` 从原始结果生成。PASS 表示该日全部检查通过，不是只过成本；固定日均有两次真实 CLI 运行。", "", "费用参考沿用 v19 的口径：MILP 优化最低许可水温及较严格 AC 辅助排热，而物理检查接受更宽的合理运行解释。因此 MILP 数值是同口径最优及宽模型的可行费用上界；oracle 的 £0.001 检查不构成所有被接受解释的全局最优证明。正成本差可与较便宜可行方案比较以证明失优，负差不能当作错误或遗憾。", ""]
    summary = {"candidates": {}}
    for cid in ["c1", "c2", "c4"]:
        folder = OUT / "candidates" / cid
        apps = read(folder / "gates-r1/apps.json")
        mutations = read(folder / "gates-r1/mutants.json")
        blind = read(folder / "blind-eval/matrix.json")
        report += [f"## {cid.upper()}", "", f"[原始历史工具矩阵](candidates/{cid}/gates-r1/apps.json) · [全部变异](candidates/{cid}/gates-r1/mutants.json)", "",
                   "| 应用 | visible | h1 | h2 | h3 | h4 | 全部通过 |", "|---|---|---|---|---|---|---|"]
        all_apps = {**apps, **(blind or {})}
        for name, result in all_apps.items():
            states = ["PASS" if result["days"][d]["passed"] else "FAIL" for d in DAYS]
            report.append("| " + " | ".join([name, *states, "是" if result["passed"] else "否"]) + " |")
        if not blind:
            report += ["| blind | 未评测 | 未评测 | 未评测 | 未评测 | 未评测 | 未完成 |"]
        report += ["", "### 失败断言", "", "| 应用 | 失败日：断言 |", "|---|---|"]
        for name, result in all_apps.items():
            errors = [d + ": " + ", ".join(x["failures"]) for d, x in result["days"].items() if x["failures"]]
            if errors:
                report.append(f"| {name} | " + "; ".join(errors) + " |")
        caught = sum(not x["passed"] for x in mutations.values())
        report += ["", f"变异抓住 **{caught}/{len(mutations)}**。", ""]
        summary["candidates"][cid] = {
            "gates": read(folder / "gates-r1/gates.json"),
            "oracle_max_abs_delta_gbp": max(abs(x["delta_gbp"]) for x in apps["oracle"]["days"].values()),
            "apps": {a: {"passed": r["passed"], "failed_days": [d for d in DAYS if not r["days"][d]["passed"]],
                         "max_seconds": max((x["seconds"] for d in r["days"].values() for x in d["runs"]),default=None)} for a, r in all_apps.items()},
            "mutants_caught": caught, "mutants_total": len(mutations)}
    fuzz = read(OUT / "candidates/c1/fuzz-200/summary.json")
    report += ["## C1：200 日差分", "", "[完整摘要](candidates/c1/fuzz-200/summary.json) · [全部输入及接受/拒绝记录](candidates/c1/fuzz-200/manifest.json)", "",
               "| 应用 | 通过日 | 失败日 | 最大单日回放及核验秒数 | 最大绝对成本差 £ |", "|---|---:|---:|---:|---:|"]
    for name, result in fuzz["apps"].items():
        delta = "n/a" if result["max_abs_delta_gbp"] is None else f"{result['max_abs_delta_gbp']:.6f}"
        report.append(f"| {name} | {result['passed_days']} | {result['failed_days']} | {result['max_seconds']:.3f} | {delta} |")
    report += ["", "本表计时包含 CLI 执行及其后的流量重算/断言，因而是 CLI 时间的上界，不是单独 CLI 的精确耗时。失败工具的成本差不能代替可行性检查；表中的最大绝对差也不等于每份工具的最大有效可行计划遗憾。具体失败原因见每一天 `runs/` 内的原始计划与 `result.json`。", ""]
    summary["fuzz"] = fuzz
    summary["fresh"] = {}
    for seed in [2026, 2403, 87123]:
        manifest = read(OUT / f"candidates/c1/fresh-{seed}/manifest.json")
        summary["fresh"][str(seed)] = {"days": len(manifest["days"]), "results": manifest["results"],
                                       "inputs_unchanged": manifest["input_hashes_unchanged_after_evaluation"]}
    summary["fresh_by_candidate"] = {}
    report += ["## 三组候选的 fresh 日", "", "每个候选独立生成并评测三个 seed，各16个接受日。下表只在该次 manifest 的评测完成标志存在时记作完成。", "",
               "| 候选 | seed | 接受日 | 评测完成 | 所有测试通过 | 输入未变 |", "|---|---:|---:|---|---|---|"]
    for cid in ["c1", "c2", "c4"]:
        summary["fresh_by_candidate"][cid] = {}
        for seed in [2026, 2403, 87123]:
            manifest = read(OUT / f"candidates/{cid}/fresh-{seed}/manifest.json")
            if manifest is None:
                report.append(f"| {cid} | {seed} | 0 | 否 | 未评测 | 未评测 |")
                continue
            complete = manifest.get("input_hashes_unchanged_after_evaluation", False)
            passed = bool(manifest["results"]) and all(not r["failed"] and not r["errors"]
                                                       for r in manifest["results"].values())
            result = {"days": len(manifest["days"]), "completed": complete,
                      "passed": passed and complete, "results": manifest["results"],
                      "inputs_unchanged": complete}
            summary["fresh_by_candidate"][cid][str(seed)] = result
            report.append(f"| {cid} | {seed} | {result['days']} | {'是' if complete else '否'} | "
                          f"{'是' if passed and complete else '未通过或未完成'} | {'是' if complete else '未完成'} |")
    decisions = read(OUT / "prechecks/DECISIONS.json")
    summary["precheck_decisions"] = decisions
    (OUT / "MATRICES.md").write_text("\n".join(report) + "\n")
    (OUT / "SUMMARY.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    print("Updated MATRICES.md and SUMMARY.json from retained evidence")


if __name__ == "__main__":
    main()
