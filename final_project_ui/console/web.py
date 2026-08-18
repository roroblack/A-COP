"""분리된 개발 콘솔 화면.

★대상의 `theme.py` 를 가져오지 않는다 (`CLAUDE.md` §0.2).
  이 프로그램의 화면은 이 프로그램이 만든다 — **대상이 하나도 없어도 떠야** 하기 때문이다.

★없는 것을 `0` 으로 채우지 않는다. `모름` 이라고 적는다.
★조용히 자르지 않는다. N개만 보이면 "전체 M개 중 M−N개는 화면에 없다" 를 적는다.
"""
from __future__ import annotations

import html
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse

from console.db import read_agent_runs, read_trace
from console.discovery import discover, inspect_path
from console.live import read_introspection
from console.profiles import profile_for
from console.readers import (judgement_counts, read_declaration, read_eval_runs,
                             read_guardrails, read_judgements)

#: 기본으로 훑을 루트. 이 저장소의 부모 = 형제 프로젝트들이 있는 곳.
DEFAULT_ROOT = Path(__file__).resolve().parents[2]

CSS = """
*,*::before,*::after{box-sizing:border-box}
:root{--bg:#f5f7fa;--surface:#fff;--line:#e3e8ef;--text:#131a26;--dim:#5d6b7f;
 --accent:#2f5bd8;--ok:#0d7a4d;--warn:#9a6200;--bad:#c0362c;--idle:#5d6b7f;
 --mono:ui-monospace,Consolas,monospace}
@media(prefers-color-scheme:dark){:root{--bg:#0d1219;--surface:#161d27;--line:#28323f;
 --text:#e7ecf3;--dim:#93a1b4;--accent:#7aa2f7;--ok:#5bd6a0;--warn:#f2bd5c;--bad:#ff8b80;--idle:#93a1b4}}
body{margin:0;background:var(--bg);color:var(--text);font-size:15px;line-height:1.55;
 font-family:system-ui,"Segoe UI","Noto Sans KR",sans-serif}
.shell{max-width:1100px;margin:0 auto;padding:1.5rem 1.25rem 4rem}
a{color:var(--accent)}
h1{font-size:1.45rem;letter-spacing:-.02em;margin:.2rem 0 .3rem}
h2{font-size:1rem;margin:0}
.lede{color:var(--dim);margin:0 0 1.5rem}
.card{background:var(--surface);border:1px solid var(--line);border-radius:12px;
 padding:1rem 1.15rem;margin-bottom:1rem}
.card h2{margin-bottom:.7rem}
.grid{display:grid;gap:.9rem;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));margin-bottom:1rem}
.stat{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:.85rem 1rem}
.stat b{display:block;font-size:1.55rem;letter-spacing:-.03em;font-variant-numeric:tabular-nums}
.stat span{font-size:.76rem;color:var(--dim);text-transform:uppercase;letter-spacing:.05em}
.stat small{color:var(--dim);font-size:.8rem}
.scroll{overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:.9rem}
th,td{text-align:left;padding:.55rem .65rem;border-bottom:1px solid var(--line);vertical-align:top}
thead th{font-size:.72rem;text-transform:uppercase;letter-spacing:.05em;color:var(--dim);white-space:nowrap}
tbody tr:last-child td{border-bottom:0}
.mono{font-family:var(--mono);white-space:nowrap}
.dim{color:var(--dim)}
.pill{display:inline-block;border-radius:99px;padding:.1rem .55rem;font-size:.76rem;font-weight:600}
.p-ok{background:#e6f6ee;color:#0d7a4d}.p-warn{background:#fff6e2;color:#9a6200}
.p-bad{background:#fdecea;color:#c0362c}.p-idle{background:#eef1f6;color:#5d6b7f}
@media(prefers-color-scheme:dark){.p-ok{background:#12332a;color:#5bd6a0}
 .p-warn{background:#3a2c12;color:#f2bd5c}.p-bad{background:#3a1c1a;color:#ff8b80}
 .p-idle{background:#212a36;color:#93a1b4}}
.note{border:1px solid currentColor;border-radius:8px;padding:.5rem .75rem;margin:.5rem 0;font-size:.88rem}
.n-warn{color:var(--warn)}.n-bad{color:var(--bad)}.n-info{color:var(--dim)}
.empty{text-align:center;color:var(--dim);padding:2.5rem 1rem;border:1px dashed var(--line);border-radius:12px}
"""


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def page(title: str, body: str, *, lede: str = "") -> HTMLResponse:
    lede_html = f"<p class='lede'>{esc(lede)}</p>" if lede else ""
    return HTMLResponse(
        "<!doctype html><html lang='ko'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{esc(title)} · 개발 콘솔</title><style>{CSS}</style></head><body>"
        f"<main class='shell'><h1>{esc(title)}</h1>{lede_html}{body}</main></body></html>")


def stat(label: str, value: Any, hint: str = "") -> str:
    hint_html = f"<small>{esc(hint)}</small>" if hint else ""
    return f"<div class='stat'><span>{esc(label)}</span><b>{esc(value)}</b>{hint_html}</div>"


def pill(text: str, kind: str = "idle") -> str:
    return f"<span class='pill p-{kind}'>{esc(text)}</span>"


def note(text: str, kind: str = "info") -> str:
    return f"<p class='note n-{kind}'>{esc(text)}</p>"


def table(headers: list[str], rows: list[str], empty: str = "없음") -> str:
    head = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = "".join(rows) or f"<tr><td class='dim' colspan='99'>{esc(empty)}</td></tr>"
    return f"<div class='scroll'><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>"


JUDGEMENT_KIND = {"통과": "ok", "부분통과": "warn", "미통과": "bad", "미착수": "idle"}


def create_app() -> FastAPI:
    app = FastAPI(title="개발 콘솔")

    @app.get("/", response_class=HTMLResponse)
    def projects(root: str = Query(default=str(DEFAULT_ROOT))) -> HTMLResponse:
        found = discover(root)
        if not found:
            return page("프로젝트", f"<div class='empty'><p>{esc(root)} 아래에 폴더가 없습니다.</p></div>",
                        lede=str(root))

        rows = []
        for item in found:
            if item.is_project:
                link = f"<a class='mono' href='/project?path={esc(item.path)}'>{esc(item.name)}</a>"
                mark = pill("프로젝트", "ok")
            else:
                # ★조용히 빼지 않는다 — "왜 내 폴더가 안 보이나" 에 답해야 한다
                link = f"<span class='mono dim'>{esc(item.name)}</span>"
                mark = pill("아님", "idle")
            rows.append(f"<tr><td>{link}</td><td>{mark}</td>"
                        f"<td class='dim'>{esc(' · '.join(item.reasons))}</td></tr>")

        n = sum(1 for i in found if i.is_project)
        summary = ("<div class='grid'>"
                   + stat("프로젝트", n, f"훑은 폴더 {len(found)}개")
                   + stat("루트", Path(root).name, str(root))
                   + "</div>")
        return page("프로젝트", summary + "<div class='card'>" +
                    table(["폴더", "판별", "근거"], rows) + "</div>",
                    lede="경로를 주지 않으면 이 콘솔의 상위 폴더를 훑습니다.")

    @app.get("/project", response_class=HTMLResponse)
    def project(path: str) -> HTMLResponse:
        found = inspect_path(path)
        if not found.is_project:
            return page("프로젝트", note(
                f"프로젝트가 아닙니다 — {' · '.join(found.reasons)}", "bad"), lede=str(path))

        target = Path(path)
        profile = profile_for(target)
        declaration = read_declaration(target)
        guardrails = read_guardrails(target)
        judgements = read_judgements(target)
        evaluation = read_eval_runs(target, limit=6)

        # ── 조립 ──────────────────────────────────────────────────────────
        if not declaration.ok:
            assembly = note(f"선언을 읽지 못했습니다 — {declaration.error}", "bad")
            head = "<div class='grid'>" + stat("모듈", "모름") + stat("Team", "모름") + "</div>"
        else:
            value = declaration.value
            modules = value["modules"]
            on = sum(1 for v in modules.values() if v is True)
            teams = value["teams"]
            active = sum(1 for t in teams if t.get("active"))
            off = [k for k, v in modules.items() if v is False]
            head = ("<div class='grid'>"
                    + stat("모듈", f"{on}/{len(modules)}", "꺼짐: " + (", ".join(off) or "없음"))
                    + stat("Agent Team", f"{active}/{len(teams)}", "라우팅됨/등록됨")
                    + stat("team_executor", value["ports"].get("team_executor") or "모름")
                    + "</div>")
            assembly = table(
                ["team_id", "active", "implementation_ref"],
                [f"<tr><td class='mono'>{esc(t.get('team_id'))}</td>"
                 f"<td>{pill('active', 'ok') if t.get('active') else pill('inactive', 'idle')}</td>"
                 f"<td class='mono dim'>{esc(t.get('implementation_ref'))}</td></tr>" for t in teams])

        # ── 막힌 것 ───────────────────────────────────────────────────────
        items = judgements.value or []
        if judgements.error and not items:
            blocked = note(f"판정을 읽지 못했습니다 — {judgements.error}", "warn")
        else:
            counts = judgement_counts(items)
            display_items = [i for i in items if i.judgement != "?듦낵"] + [
                i for i in items if i.judgement == "?듦낵"]
            stuck = [i for i in items if i.judgement != "통과"]
            rows = [f"<tr><td class='mono'>{esc(i.id)}</td>"
                    f"<td>{pill(i.judgement, JUDGEMENT_KIND.get(i.judgement, 'bad'))}</td>"
                    f"<td>{esc(i.title)}</td>"
                    f"<td class='dim'>{'재현' if i.has_reproduction else '재현 없음'} · "
                    f"{'실측' if i.has_actual_output else '실측 없음'}</td></tr>" for i in stuck]
            # ★점수 하나로 뭉치지 않는다 — 부분통과와 미착수는 다른 일이다
            distribution = " ".join(
                pill(f"{k} {v}", JUDGEMENT_KIND.get(k, "bad")) for k, v in sorted(counts.items()))
            blocked = (f"<p>{distribution}</p>"
                       + (table(["DoD", "판정", "항목", "근거"], rows) if stuck
                          else note("통과가 아닌 항목이 없습니다.", "info")))

        # ── 평가 ─────────────────────────────────────────────────────────
        data = evaluation.value or {"runs": [], "total": 0, "shown": 0}
        if evaluation.error and not data["runs"]:
            evaluated = note(f"평가를 읽지 못했습니다 — {evaluation.error}", "warn")
        elif not data["runs"]:
            evaluated = "<div class='empty'><p>평가 리포트가 없습니다.</p></div>"
        else:
            rows = []
            for run in data["runs"]:
                marks = [pill("mock — 실제 성능 아님", "bad")] if run.is_mock else []
                marks += [pill(a, "warn") for a in run.ablations]
                rows.append(
                    f"<tr><td class='mono'>{esc(run.file)}</td>"
                    f"<td class='mono'>{esc(run.rows)}</td>"
                    f"<td>{esc(run.arm or '미표기')}</td>"
                    f"<td>{esc(run.provider or '미표기')}</td>"
                    # ★실측과 추정을 나란히 둔다. 하나로 뭉치면 거짓이 된다.
                    f"<td class='mono'>{'모름' if run.observed_cost_usd is None else f'${run.observed_cost_usd}'}</td>"
                    f"<td class='mono dim'>{'모름' if run.estimated_cost_usd is None else f'${run.estimated_cost_usd}'}</td>"
                    f"<td>{''.join(marks) or '<span class=dim>—</span>'}</td></tr>")
            # ★말없이 자르지 않는다
            cut = (note(f"최근 {data['shown']}개만 표시했습니다. 전체 {data['total']}개 중 "
                        f"{data['total'] - data['shown']}개는 화면에 없습니다.", "warn")
                   if data["total"] > data["shown"] else "")
            evaluated = (note("run 단위로만 비교합니다. arm·dataset·실행 방식이 다르면 "
                              "평균을 견줄 수 없습니다.", "info") + cut
                         + table(["리포트", "행", "arm", "provider", "실측 비용", "추정 비용", "표시"], rows))

        live = read_introspection(profile.introspection_url, profile.contract_versions,
                                   profile.introspection_token)
        runs = read_agent_runs(profile.database_url)
        state_rows = []
        if runs.state_counts:
            for table_name, counts in runs.state_counts.items():
                for status, count in counts.items():
                    state_rows.append(f"<tr><td>{esc(table_name)}</td>"
                                     f"<td>{esc(status)}</td><td>{esc(count)}</td></tr>")
        # ★상태 분포. `outbox` 의 `unknown`·`dead_letter` 는 **사람이 봐야 하는 상태**다.
        #   `unknown` 은 돈이 나갔는지 모르는 상태이므로 가장 세게 칠한다.
        state_rows = []
        for table_name, counts in (runs.state_counts or {}).items():
            if "__error__" in counts:
                # ★읽지 못한 것을 0 으로 채우지 않는다
                state_rows.append(f"<tr><td>{esc(table_name)}</td>"
                                  f"<td colspan='2' class='dim'>읽지 못했다 — "
                                  f"{esc(counts['__error__'])}</td></tr>")
                continue
            if not counts:
                state_rows.append(f"<tr><td>{esc(table_name)}</td>"
                                  f"<td colspan='2' class='dim'>행 없음</td></tr>")
                continue
            for status, count in sorted(counts.items(), key=lambda x: -x[1]):
                kind = "bad" if status in ("unknown", "dead_letter", "escalated") else (
                    "warn" if status in ("waiting_approval", "waiting_input", "pending") else "idle")
                state_rows.append(f"<tr><td class='dim'>{esc(table_name)}</td>"
                                  f"<td>{pill(status, kind)}</td>"
                                  f"<td class='mono'>{esc(count)}</td></tr>")

        state_card = "<div class='card'><h2>상태 분포</h2>" + table(
            ["테이블", "status", "건수"], state_rows,
            # ★연결이 없으면 "0" 이 아니라 그 이유를 적는다
            empty=runs.detail or "연결 안 함") + "</div>"
        run_rows = []
        for run in runs.rows:
            run_id = run.get("run_id")
            href = f"/run?path={esc(str(target))}&run_id={esc(run_id)}"
            run_rows.append(
                f"<tr><td class='mono'><a href='{href}'>{esc(run_id)}</a></td>"
                f"<td>{esc(run.get('status'))}</td>"
                f"<td class='mono'>{esc(run.get('case_id'))}</td>"
                f"<td class='dim'>{esc(run.get('started_at'))}</td></tr>")
        run_history = table(
            ["run_id", "status", "case_id", "started_at"], run_rows,
            empty=runs.detail or "실행 이력이 없습니다.")

        connections = table(
            ["출처", "상태", "세부"],
            [f"<tr><td>{esc(label)}</td><td>{pill(result.status, 'ok' if result.status == '읽음' else 'idle')}</td>"
             f"<td class='dim'>{esc(result.detail)}</td></tr>"
             for label, result in (
                 ("선언", type("R", (), {"status": "읽음" if declaration.ok else "모름", "detail": declaration.source or ""})()),
                 ("판정", type("R", (), {"status": "읽음" if judgements.ok else "모름", "detail": judgements.source or ""})()),
                 ("평가", type("R", (), {"status": "읽음" if evaluation.ok else "모름", "detail": evaluation.source or ""})()),
                 ("조립 실측", live),
                 ("실행 이력", runs),
             )],
            empty="연결 정보가 없습니다.")

        guardrail_value = "missing"
        if guardrails.ok:
            context = guardrails.value.get("context", {})
            guardrail_value = context.get("token_budget", "missing")
        guardrail_card = (
            "<div class='card'><h2>guardrails</h2>" +
            table(["context.token_budget"], [f"<tr><td class='mono'>{esc(guardrail_value)}</td></tr>"],
                  empty=guardrails.error or "missing") + "</div>")

        body = (head
                + guardrail_card
                + f"<div class='card'><h2>조립</h2>{assembly}</div>"
                + f"<div class='card'><h2>무엇이 막혀 있나</h2>{blocked}</div>"
                + f"<div class='card'><h2>평가 실행</h2>{evaluated}</div>"
                # ★state_card 를 만들어 놓고 body 에 안 넣고 있었다 —
                #   섹션이 통째로 화면에서 사라졌고, 테스트가 없어 아무도 몰랐다.
                + state_card
                + "<div class='card'><h2>실행 이력</h2>" + run_history + "</div>"
                + f"<div class='card'><h2>연결</h2>{connections}</div>"
                + f"<p><a href='/'>← 프로젝트 목록</a></p>")
        return page(found.name, body, lede=str(target))

    @app.get("/run", response_class=HTMLResponse)
    def run(path: str = Query(default=""), run_id: str | None = Query(default=None)) -> HTMLResponse:
        if not run_id:
            return page("실행 추적", note("run_id가 없습니다.", "warn"), lede=path)

        target = Path(path) if path else Path(DEFAULT_ROOT)
        profile = profile_for(target)
        result = read_trace(profile.database_url, run_id)
        if not result.ok:
            kind = "warn" if result.status in ("연결 안 함", "그 실행이 없다") else "bad"
            return page("실행 추적", note(result.detail or result.status, kind), lede=str(target))

        sections = []
        for item in result.trace:
            stage = item.get("stage", "")
            if "error" in item:
                content = note(f"읽지 못했습니다: {item['error']}", "warn")
            else:
                rows = item.get("rows", [])
                if not rows:
                    content = note("이 단계의 기록이 없습니다.", "info")
                else:
                    headers = list(rows[0].keys())
                    rendered = [
                        "<tr>" + "".join(f"<td>{esc(row.get(header))}</td>" for header in headers) + "</tr>"
                        for row in rows
                    ]
                    content = table(headers, rendered)
            sections.append(f"<div class='card'><h2>{esc(stage)}</h2>{content}</div>")

        back = f"<p><a href='/project?path={esc(str(target))}'>실행 이력으로 돌아가기</a></p>"
        return page("실행 추적", "".join(sections) + back, lede=f"{target} · {run_id}")

    return app


app = create_app()


def main() -> None:
    """★포트를 하드코딩하지 않는다. 호스트가 `PORT` 로 지정한다 —
    다른 채팅이 띄운 서버와 포트가 부딪히면 아예 뜨지 못한다."""
    import uvicorn
    uvicorn.run("console.web:app", host="127.0.0.1",
                port=int(os.environ.get("PORT", "8060")), reload=True)


if __name__ == "__main__":
    main()
