from __future__ import annotations

import json
import os
import time
import csv
import re
import unicodedata

from flask import Flask, jsonify, send_from_directory
from flask import request
from flask_sock import Sock

from services.leitor_serial import iniciar_leitura_serial as iniciar_leitor, obter_estado_serial

app = Flask(__name__, static_folder="static", static_url_path="/static")
sock = Sock(app)


@app.get("/")
def index() -> str:
	return send_from_directory(app.static_folder, "index.html")


@app.get("/api/estado")
def api_estado():
	return jsonify(obter_estado_serial())


@app.get("/api/logs")
def api_logs():
	"""Retorna metadados do arquivo de logs de detecções."""
	repo_root = os.path.abspath(os.path.dirname(__file__))
	log_path = os.path.join(repo_root, "logs", "detections.log")
	if not os.path.exists(log_path):
		return jsonify({"exists": False, "size_bytes": 0, "entries": 0})

	size = os.path.getsize(log_path)
	# Conta linhas (entradas)
	try:
		with open(log_path, "r", encoding="utf-8") as fh:
			entries = sum(1 for _ in fh)
	except Exception:
		entries = 0

	return jsonify({"exists": True, "size_bytes": size, "entries": entries})


@app.get("/api/logs/content")
def api_logs_content():
	"""Retorna um trecho do arquivo de logs como JSON.

	Query params:
	- start: índice da linha inicial (0-based). Default: 0 (início do arquivo)
	- lines: número de linhas a retornar. Default: 200
	"""
	repo_root = os.path.abspath(os.path.dirname(__file__))
	log_path = os.path.join(repo_root, "logs", "detections.log")
	if not os.path.exists(log_path):
		return jsonify({"exists": False, "total": 0, "lines": []})

	try:
		start = int(request.args.get("start", "0"))
	except Exception:
		start = 0
	try:
		count = int(request.args.get("lines", "200"))
	except Exception:
		count = 200

	try:
		with open(log_path, "r", encoding="utf-8") as fh:
			all_lines = [ln.rstrip("\n") for ln in fh]
	except Exception:
		return jsonify({"exists": False, "total": 0, "lines": []})

	total = len(all_lines)
	# clamp start
	if start < 0:
		start = 0
	if start >= total:
		return jsonify({"exists": True, "total": total, "lines": []})

	slice_end = min(total, start + count)
	segment = all_lines[start:slice_end]
	return jsonify({"exists": True, "total": total, "start": start, "lines": segment})


@app.get("/api/logs/parsed")
def api_logs_parsed():
	"""Retorna um trecho do arquivo de logs parseado como objetos JSON.

	Query params:
	- start: índice da linha inicial de dados (0-based, header não conta). Default: 0
	- lines: número de linhas a retornar. Default: 200
	"""
	repo_root = os.path.abspath(os.path.dirname(__file__))
	log_path = os.path.join(repo_root, "logs", "detections.log")
	if not os.path.exists(log_path):
		return jsonify({"exists": False, "total": 0, "entries": []})

	try:
		start = int(request.args.get("start", "0"))
	except Exception:
		start = 0
	try:
		count = int(request.args.get("lines", "200"))
	except Exception:
		count = 200

	try:
		with open(log_path, "r", encoding="utf-8") as fh:
			rows = list(csv.reader(fh))
	except Exception:
		return jsonify({"exists": False, "total": 0, "entries": []})

	if not rows:
		return jsonify({"exists": True, "total": 0, "entries": []})

	def _normalize_header(s: str) -> str:
		s = (s or "").strip().lower()
		s = unicodedata.normalize("NFKD", s)
		s = "".join(ch for ch in s if not unicodedata.combining(ch))
		s = re.sub(r"[^a-z0-9]+", "_", s)
		return s.strip("_")

	header = [_normalize_header(h) for h in rows[0]]
	data_rows = rows[1:]
	total = len(data_rows)

	if start < 0:
		start = 0
	if start >= total:
		return jsonify({"exists": True, "total": total, "entries": []})

	slice_end = min(total, start + count)
	segment = data_rows[start:slice_end]

	def to_number(x):
		try:
			return float(x)
		except Exception:
			return None

	entries = []
	for r in segment:
		cells = [c.strip() for c in r]
		rowd = {header[i]: cells[i] if i < len(cells) else "" for i in range(len(header))}

		ts = rowd.get('timestamp') or rowd.get('time') or rowd.get('date') or rowd.get('datetime') or ''
		angle = None
		dist = None
		temp = None
		portao = None
		deteccao = None
		for k in rowd:
			if angle is None and ('angle' in k or 'angulo' in k):
				angle = rowd.get(k)
			if dist is None and ('distance' in k or 'distancia' in k):
				dist = rowd.get(k)
			if temp is None and ('temp' in k or 'temperatura' in k):
				temp = rowd.get(k)
			if portao is None and ('port' in k or 'porta' in k or 'gate' in k):
				portao = rowd.get(k)
			if deteccao is None and ('detecc' in k or 'detect' in k or 'humano' in k):
				deteccao = rowd.get(k)

		entries.append({
			'timestamp': ts,
			'angle': to_number(angle),
			'distance_cm': to_number(dist),
			'temperature_c': to_number(temp),
			'portao': (portao or None),
			'deteccao': (deteccao or None),
		})

	return jsonify({"exists": True, "total": total, "start": start, "entries": entries})


@app.get("/logs/download")
def download_logs():
	repo_root = os.path.abspath(os.path.dirname(__file__))
	logs_dir = os.path.join(repo_root, "logs")
	log_file = "detections.log"
	if not os.path.exists(os.path.join(logs_dir, log_file)):
		return ("Arquivo de log não encontrado", 404)
	# send_from_directory para forçar download
	return send_from_directory(logs_dir, log_file, as_attachment=True)


@sock.route("/ws")
def websocket_monitor(ws):
	while True:
		ws.send(json.dumps(obter_estado_serial(), ensure_ascii=False))
		time.sleep(0.25)


if __name__ == "__main__":
	porta_arduino = os.getenv("SERIAL_PORT", None)
	if porta_arduino:
		print(f"[SERIAL] Usando porta explícita: {porta_arduino}")
	else:
		print("[SERIAL] Auto-detectando porta...")

	# Evita que o leitor serial seja iniciado duas vezes quando o Flask
	# roda em modo debug com o reloader (que reinicia o processo).
	# Inicia o leitor apenas no processo principal do reloader (WERKZEUG_RUN_MAIN="true").
	if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
		print("[SERIAL] Iniciando leitura da porta serial do Arduino...")
		iniciar_leitor(porta=porta_arduino)

	app.run(host="0.0.0.0", port=5000, debug=True)