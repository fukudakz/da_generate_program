#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
学会プログラム HTML 生成スクリプト

データソース:
- input/session.csv  （セッション情報）
- input/talk.csv     （各セッション内の発表）
- input/conference_name.txt  （ページタイトル / 見出し）

出力:
- output/program.html （プログラムページ HTML）

使い方:
    python3 generate_program_html.py
"""

import csv
import html as html_lib
import re
from pathlib import Path
from collections import defaultdict, OrderedDict
from datetime import datetime

BASE_DIR = Path(__file__).parent
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"

SESSION_CSV = INPUT_DIR / "session.csv"
TALK_CSV = INPUT_DIR / "talk.csv"
OUTPUT_HTML = OUTPUT_DIR / "program.html"
CONFERENCE_NAME_TXT = INPUT_DIR / "conference_name.txt"

PAGE_CSS = """
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Helvetica Neue', Arial, 'Hiragino Kaku Gothic ProN', 'Meiryo', sans-serif;
      line-height: 1.7;
      font-size: 15px;
      color: #333;
      background: #f5f5f5;
      margin: 0;
      padding: 0;
    }
    .page-wrap {
      max-width: 960px;
      margin: 0 auto;
      padding: 32px 16px 64px;
      background: #fff;
    }
    h1 {
      font-size: 26px;
      margin-top: 0;
      margin-bottom: 24px;
      border-bottom: 2px solid #e5e5e5;
      padding-bottom: 8px;
    }
    h2 {
      font-size: 20px;
      margin-top: 32px;
      margin-bottom: 12px;
      border-left: 4px solid #0066cc;
      padding-left: 8px;
    }
    h3 {
      font-size: 17px;
      margin-top: 20px;
      margin-bottom: 8px;
      color: #0066cc;
    }
    h4 {
      font-size: 15px;
      margin: 18px 0 8px;
      color: #0066cc;
    }
    .date-block { margin-top: 24px; }
    .session {
      margin: 8px 0 14px;
      padding: 8px 12px 10px;
      border: 1px solid #e1e1e1;
      border-radius: 3px;
      background: #fafafa;
    }
    .session-header { margin-bottom: 4px; }
    .session-location { font-size: 13px; color: #555; }
    .session-title {
      font-size: 16px;
      font-weight: 600;
      color: #0066cc;
      margin-top: 2px;
    }
    .session-meta { font-size: 13px; color: #666; margin-bottom: 4px; }
    .talk-list { margin: 6px 0 0 1.5em; padding: 0; }
    .talk-list li { margin-bottom: 6px; }
    .talk-title { font-weight: 600; }
    .talk-authors { font-size: 13px; color: #555; }
    .schedule-table-wrap { margin-top: 8px; margin-bottom: 18px; }
    /* WordPress テーマ（#content tr td など）より優先する */
    .page-wrap .schedule-table {
      border-collapse: collapse !important;
      width: 100% !important;
      table-layout: fixed !important;
      font-size: 13px !important;
      margin: 0 0 18px !important;
      text-align: center !important;
      border: 1px solid #ddd !important;
    }
    .page-wrap .schedule-table th,
    .page-wrap .schedule-table td {
      border: 1px solid #ddd !important;
      padding: 4px 6px !important;
      text-align: center !important;
      vertical-align: top !important;
      color: #333 !important;
      line-height: 1.5 !important;
    }
    .page-wrap .schedule-table thead th {
      background: #f0f4f8 !important;
      font-weight: 600 !important;
      font-size: 13px !important;
    }
    .page-wrap .schedule-time {
      white-space: nowrap !important;
      background: #f9fafb !important;
    }
    .page-wrap .schedule-table td {
      font-size: 12px !important;
      background: #fff !important;
    }
    .page-wrap .schedule-table a { color: #0066cc !important; text-decoration: none !important; }
    .page-wrap .schedule-table a:hover { text-decoration: underline !important; }
    @media screen and (max-width: 600px) {
      .page-wrap { padding: 16px 8px 40px; }
      h1 { font-size: 22px; }
      h2 { font-size: 18px; }
      h3 { font-size: 16px; }
    }
"""

# テーマの要素セレクタより優先される。style 属性は <style> が削られても残る。
TABLE_STYLE = (
    "border-collapse:collapse;width:100%;table-layout:fixed;font-size:13px;"
    "margin:0 0 18px;text-align:center;border:1px solid #ddd;"
)
TH_STYLE = (
    "border:1px solid #ddd;padding:4px 6px;text-align:center;vertical-align:top;"
    "background:#f0f4f8;font-weight:600;font-size:13px;color:#333;line-height:1.5;"
)
TIME_TH_STYLE = TH_STYLE + "white-space:nowrap;background:#f9fafb;"
TD_STYLE = (
    "border:1px solid #ddd;padding:4px 6px;text-align:center;vertical-align:top;"
    "font-size:12px;color:#333;line-height:1.5;background:#fff;"
)
LINK_STYLE = "color:#0066cc;text-decoration:none;"


def read_sessions(path: Path):
    """session.csv を読み込んで辞書にする"""
    sessions = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # セッションIDは文字列のまま扱う（CSV内のIDと一致させるため）
            sessions.append(
                {
                    "id": row["セッションID"].strip(),
                    "name": row["セッション名"].strip(),
                    "date": row["日付"].strip(),
                    "time": row["時間"].strip(),
                    "chair": row["座長"].strip(),
                    "room": row["会場"].strip(),
                }
            )
    return sessions


def read_talks(path: Path):
    """talk.csv を読み込んでセッションIDごとにグループ化"""
    talks_by_session = defaultdict(list)
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            session_id = row["所属するセッション"].strip()
            talks_by_session[session_id].append(
                {
                    "id": row["発表ID"].strip(),
                    "easychair_id": row["easychair_paper_ID"].strip(),
                    "authors": row["著者"].strip(),
                    "title": row["タイトル"].strip(),
                }
            )

    # 各セッション内の発表を発表IDでソート
    for sid, talks in talks_by_session.items():
        talks.sort(key=lambda t: int(t["id"]) if t["id"].isdigit() else t["id"])

    return talks_by_session


def format_date_jp(date_str: str) -> str:
    """YYYY-M-D または YYYY-MM-DD 形式の日付を「YYYY年M月D日(曜)」に整形"""
    parts = date_str.split("-")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        return date_str
    dt = datetime(int(parts[0]), int(parts[1]), int(parts[2]))
    weekday_map = ["月", "火", "水", "木", "金", "土", "日"]
    return f"{dt.year}年{dt.month}月{dt.day}日（{weekday_map[dt.weekday()]}）"


def read_conference_name(path: Path) -> str:
    """input/conference_name.txt の最初の空でない行を大会名にする。"""
    if not path.exists():
        raise FileNotFoundError(f"大会名ファイルがありません: {path}")
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        name = line.strip()
        if name:
            return name
    raise ValueError(f"{path} が空です。大会名を1行書いてください。")


_TIME_PATTERN = re.compile(r"(\d{1,2}):(\d{2})")
_ROOM_NUMBER = re.compile(r"\d+")


def room_sort_key(room: str):
    """部屋番号の昇順。番号が無い会場（後日公開など）は右端。"""
    numbers = tuple(int(n) for n in _ROOM_NUMBER.findall(room))
    if not numbers:
        return (1, room)
    return (0, numbers, room)


def get_rooms_sorted_for_timetable(sess_list):
    """タイムテーブルの列順。21号館312, 313, … のあと、番号の無い会場。"""
    all_rooms = {s["room"] for s in sess_list}
    return sorted(all_rooms, key=room_sort_key)


def start_time_key(time_str: str):
    """時間文字列から開始時刻を (hour, minute) のタプルで返す"""
    # 区切り記号（全角/半角の波ダッシュなど）で開始時刻部分を取り出す
    for sep in ("〜", "～", "-", "―", "−"):
        if sep in time_str:
            time_str = time_str.split(sep)[0]
            break
    m = _TIME_PATTERN.search(time_str)
    if not m:
        # パースできない場合は末尾に回す
        return (99, 99)
    h = int(m.group(1))
    mi = int(m.group(2))
    return (h, mi)


def group_sessions_by_date(sessions):
    """日付ごとにセッションをグループ化して、日付・時間順にソート"""
    grouped = defaultdict(list)
    for s in sessions:
        grouped[s["date"]].append(s)

    # 日付順にソートされた OrderedDict を返す
    def sort_key_date(d):
        try:
            return datetime.strptime(d, "%Y-%m-%d")
        except ValueError:
            return d

    ordered = OrderedDict()
    for date in sorted(grouped.keys(), key=sort_key_date):
        # 各日付内で開始時刻順にソート
        grouped[date].sort(key=lambda s: start_time_key(s["time"]))
        ordered[date] = grouped[date]
    return ordered


def generate_html(sessions, talks_by_session, conference_name: str):
    """HTML文字列を生成"""
    grouped = group_sessions_by_date(sessions)
    title = html_lib.escape(conference_name)

    html = []
    html.append("<!DOCTYPE html>")
    html.append('<html lang="ja">')
    html.append("<head>")
    html.append('  <meta charset="UTF-8">')
    html.append('  <meta name="viewport" content="width=device-width, initial-scale=1">')
    html.append(f"  <title>{title}</title>")
    html.append("</head>")
    html.append("<body>")
    html.append('<div class="page-wrap">')
    # <style> を本文側に置く。WordPress ではこの div ごとカスタムHTMLへ貼る。
    html.append(f"<style>{PAGE_CSS}</style>")

    html.append(f"<h1>{title}</h1>")

    # まず全日程のタイムテーブルをまとめて表示
    html.append("<h2>タイムテーブル</h2>")
    for date_str, sess_list in grouped.items():
        html.append('<div class="date-block">')
        html.append(f"  <h3>{format_date_jp(date_str)}</h3>")

        rooms = get_rooms_sorted_for_timetable(sess_list)
        rooms = [r for r in rooms if r] or [""]
        times = sorted({s["time"] for s in sess_list}, key=start_time_key)
        hide_room_header = rooms == [""]

        if times:
            time_room_index = defaultdict(list)
            for s in sess_list:
                key_room = s["room"] if not hide_room_header else ""
                time_room_index[(s["time"], key_room)].append(s)

            html.append('  <div class="schedule-table-wrap">')
            html.append(f'    <table class="schedule-table" style="{TABLE_STYLE}">')
            html.append("      <thead>")
            html.append("        <tr>")
            html.append(f'          <th class="schedule-time" style="{TIME_TH_STYLE}">時間</th>')
            if hide_room_header:
                html.append(f'          <th style="{TH_STYLE}">内容</th>')
            else:
                for room in rooms:
                    html.append(f'          <th style="{TH_STYLE}">{html_lib.escape(room)}</th>')
            html.append("        </tr>")
            html.append("      </thead>")
            html.append("      <tbody>")
            for t in times:
                html.append("        <tr>")
                html.append(
                    f'          <th class="schedule-time" style="{TIME_TH_STYLE}">{html_lib.escape(t)}</th>'
                )
                cols = rooms
                for room in cols:
                    cell_sessions = time_room_index.get((t, room), [])
                    if cell_sessions:
                        links = "<br>".join(
                            f'<a href="#session-{html_lib.escape(ses["id"])}" style="{LINK_STYLE}">{html_lib.escape(ses["name"])}</a>'
                            for ses in cell_sessions
                        )
                        html.append(f'          <td style="{TD_STYLE}">{links}</td>')
                    else:
                        html.append(f'          <td style="{TD_STYLE}"></td>')
                html.append("        </tr>")
            html.append("      </tbody>")
            html.append("    </table>")
            html.append("  </div>")

        html.append("</div>")  # .date-block

    # 続いてプログラム詳細を表示
    html.append("<h2>プログラム詳細</h2>")

    for date_str, sess_list in grouped.items():
        html.append('<div class="date-block">')
        html.append(f"  <h3>{format_date_jp(date_str)}</h3>")

        # 同じ時間帯のセッションをまとめる（詳細リスト）
        sessions_by_time = defaultdict(list)
        for s in sess_list:
            sessions_by_time[s["time"]].append(s)

        # 時間順に出力（開始時刻でソート）
        for time_str in sorted(sessions_by_time.keys(), key=start_time_key):
            html.append(f"  <h4>{html_lib.escape(time_str)}</h4>")

            # 同じ時間帯のセッションは教室名（room）でソート
            for s in sorted(sessions_by_time[time_str], key=lambda x: x["room"]):
                sid = s["id"]
                anchor_id = f"session-{html_lib.escape(sid)}"
                html.append('  <div class="session">')
                html.append('    <div class="session-header">')
                if s["room"]:
                    html.append(f'      <div class="session-location">{html_lib.escape(s["room"])}</div>')
                html.append(f'      <div class="session-title" id="{anchor_id}">{html_lib.escape(s["name"])}</div>')
                html.append("    </div>")
                if s["chair"]:
                    html.append(f'    <div class="session-meta">座長：{html_lib.escape(s["chair"])}</div>')

                talks = talks_by_session.get(sid, [])
                if talks:
                    html.append('    <ol class="talk-list">')
                    for t in talks:
                        html.append("      <li>")
                        html.append(f'        <div class="talk-title">{html_lib.escape(t["title"])}</div>')
                        if t["authors"]:
                            html.append(f'        <div class="talk-authors">{html_lib.escape(t["authors"])}</div>')
                        html.append("      </li>")
                    html.append("    </ol>")

                html.append("  </div>")  # .session

        html.append("</div>")  # .date-block

    html.append("</div>")  # .page-wrap
    html.append("</body>")
    html.append("</html>")

    return "\n".join(html)


def main():
    if not SESSION_CSV.exists():
        print(f"エラー: {SESSION_CSV} が見つかりません")
        return
    if not TALK_CSV.exists():
        print(f"エラー: {TALK_CSV} が見つかりません")
        return
    if not CONFERENCE_NAME_TXT.exists():
        print(f"エラー: {CONFERENCE_NAME_TXT} が見つかりません")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("セッション情報を読み込み中...")
    sessions = read_sessions(SESSION_CSV)
    print(f"  セッション数: {len(sessions)}")

    print("発表情報を読み込み中...")
    talks_by_session = read_talks(TALK_CSV)
    total_talks = sum(len(v) for v in talks_by_session.values())
    print(f"  発表数: {total_talks}")

    conference_name = read_conference_name(CONFERENCE_NAME_TXT)
    print(f"  大会名: {conference_name}")

    print("HTMLを生成中...")
    html = generate_html(sessions, talks_by_session, conference_name)

    OUTPUT_HTML.write_text(html, encoding="utf-8")
    print(f"完了: {OUTPUT_HTML} を生成しました")


if __name__ == "__main__":
    main()

