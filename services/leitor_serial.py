from __future__ import annotations

import threading
import time
import os
import json
from datetime import datetime, timezone
from typing import Any

try:
	import serial
	from serial.tools import list_ports
except ImportError as import_error:
	serial = None
	list_ports = None
	_IMPORT_ERROR = import_error
else:
	_IMPORT_ERROR = None

from services.tratamento_dados import interpretar_linha, tratar_erro_serial

DADO_SERIAL: dict[str, Any] | None = None
LINHA_SERIAL: str | None = None
SERIAL_CONECTADO = False
SERIAL_ERRO: str | None = None
ULTIMA_CONEXAO: str | None = None
ULTIMO_LOG_HUMANO: float = 0  # Timestamp do último log de humano gravado

_LOCK = threading.Lock()
_STOP_EVENT = threading.Event()
_THREAD: threading.Thread | None = None


def descobrir_porta_serial(porta: str | None = None) -> str:
	if porta:
		return porta
	if list_ports is None:
		raise RuntimeError("pyserial nao esta instalado. Instale com: pip install pyserial") from _IMPORT_ERROR

	portas = list(list_ports.comports())
	if not portas:
		raise RuntimeError("Nenhuma porta serial encontrada no sistema.")

	return portas[0].device


def obter_dado_serial() -> dict[str, Any] | None:
	with _LOCK:
		return None if DADO_SERIAL is None else dict(DADO_SERIAL)


def obter_estado_serial() -> dict[str, Any]:
	with _LOCK:
		return {
			"conectado": SERIAL_CONECTADO,
			"erro": SERIAL_ERRO,
			"linha": LINHA_SERIAL,
			"dado": None if DADO_SERIAL is None else dict(DADO_SERIAL),
			"ultima_conexao": ULTIMA_CONEXAO,
		}


def parar_leitura_serial() -> None:
	global SERIAL_CONECTADO

	_STOP_EVENT.set()
	with _LOCK:
		SERIAL_CONECTADO = False


def iniciar_leitura_serial(
	porta: str | None = None,
	baudrate: int = 9600,
	timeout: float = 1.0,
) -> threading.Thread:
	global _THREAD

	if serial is None:
		raise RuntimeError("pyserial nao esta instalado. Instale com: pip install pyserial") from _IMPORT_ERROR

	if _THREAD is not None and _THREAD.is_alive():
		return _THREAD

	_STOP_EVENT.clear()
	_THREAD = threading.Thread(
		target=_loop_serial,
		args=(porta, baudrate, timeout),
		daemon=True,
	)
	_THREAD.start()
	return _THREAD


def _salvar_estado(*, conectado: bool, erro: str | None = None, porta: str | None = None, baudrate: int | None = None, raw: str | None = None, parsed: Any = None) -> None:
	global DADO_SERIAL, LINHA_SERIAL, SERIAL_CONECTADO, SERIAL_ERRO, ULTIMA_CONEXAO

	with _LOCK:
		SERIAL_CONECTADO = conectado
		SERIAL_ERRO = erro
		if conectado:
			ULTIMA_CONEXAO = datetime.now(timezone.utc).isoformat()
		if raw is not None:
			LINHA_SERIAL = raw
			DADO_SERIAL = {
				"porta": porta,
				"baudrate": baudrate,
				"raw": raw,
				"parsed": parsed,
			}


def _log_detection(parsed: Any, raw: str | None, porta: str | None, baudrate: int | None) -> bool:
	"""Grava detecção de Humano em CSV com intervalo mínimo de 5s."""
	global ULTIMO_LOG_HUMANO
	
	agora = time.time()
	
	# Intervalo mínimo de 5 segundos entre logs
	if agora - ULTIMO_LOG_HUMANO < 5.0:
		return False
	
	try:
		repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
		logs_dir = os.path.join(repo_root, "logs")
		os.makedirs(logs_dir, exist_ok=True)
		log_file = os.path.join(logs_dir, "detections.log")

		arquivo_existe = os.path.exists(log_file)
		timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
		angulo_val = parsed.get("angulo")
		distancia_val = parsed.get("distancia_cm")
		temperatura_val = parsed.get("temperatura_objeto_c")

		def _fmt(v):
			try:
				return f"{float(v):.2f}"
			except Exception:
				return "?"

		angulo_s = _fmt(angulo_val)
		distancia_s = _fmt(distancia_val)
		temperatura_s = _fmt(temperatura_val)

		with open(log_file, "a", encoding="utf-8") as fh:
			if not arquivo_existe:
				fh.write("timestamp,angle,distance_cm,temperature_c,portao,deteccao,raw\n")

			portao_val = parsed.get("portao") if isinstance(parsed, dict) else None
			deteccao_val = parsed.get("deteccao") if isinstance(parsed, dict) else None
			raw_val = (raw or "")
			raw_escaped = raw_val.replace('"', '""')
			portao_s = (str(portao_val).upper() if portao_val is not None else "-")
			deteccao_s = (str(deteccao_val) if deteccao_val is not None else "-")

			fh.write(f"{timestamp},{angulo_s},{distancia_s},{temperatura_s},{portao_s},{deteccao_s},\"{raw_escaped}\"\n")
		ULTIMO_LOG_HUMANO = agora
		return True
	except Exception:
		# Não propaga erro para evitar parada da thread de leitura
		return False


def _loop_serial(porta: str | None, baudrate: int, timeout: float) -> None:
	try:
		porta_serial = descobrir_porta_serial(porta)
		print(f"[SERIAL] Porta detectada: {porta_serial}")
	except Exception as exc:
		msg_erro = tratar_erro_serial(exc)
		print(f"[SERIAL] ERRO ao descobrir porta: {msg_erro}")
		_salvar_estado(conectado=False, erro=msg_erro, porta=porta, baudrate=baudrate)
		return

	tentativa = 0
	while not _STOP_EVENT.is_set():
		try:
			tentativa += 1
			print(f"[SERIAL] Tentativa {tentativa}: conectando em {porta_serial}@{baudrate}...")
			with serial.Serial(porta_serial, baudrate, timeout=timeout) as conexao:
				tentativa = 0
				print(f"[SERIAL] Conectado com sucesso em {porta_serial}")
				_salvar_estado(conectado=True, erro=None, porta=porta_serial, baudrate=baudrate)

				while not _STOP_EVENT.is_set():
					linha = conexao.readline()
					if not linha:
						continue

					texto = linha.decode("utf-8", errors="ignore").strip()
					parsed = interpretar_linha(texto)

					try:
						print(f"[SERIAL] RAW LINE: {texto}")
						print(f"[SERIAL] PARSED: {json.dumps(parsed, ensure_ascii=False)}")
					except Exception:
						pass

					_salvar_estado(
						conectado=True,
						erro=None,
						porta=porta_serial,
						baudrate=baudrate,
						raw=texto,
						parsed=parsed,
					)

					# Se for um dicionário parseado e deteccao == 'Humano', grava log offline
					try:
						if isinstance(parsed, dict) and parsed.get("deteccao") == "Humano":
							foi_gravado = _log_detection(parsed, texto, porta_serial, baudrate)
							if foi_gravado:
								print(f"[SERIAL] ✓ Detecção de Humano registrada no log")
							else:
								print(f"[SERIAL] · Detecção de Humano (intervalo mínimo não atingido)")
					except Exception:
						pass
		except Exception as excecao:
			msg_erro = tratar_erro_serial(excecao)
			print(f"[SERIAL] ERRO: {msg_erro}")
			_salvar_estado(
				conectado=False,
				erro=msg_erro,
				porta=porta_serial,
				baudrate=baudrate,
			)
			if not _STOP_EVENT.is_set():
				espera = min(5, tentativa)
				print(f"[SERIAL] Aguardando {espera}s antes de tentar novamente...")
				time.sleep(espera)


def main() -> None:
	iniciar_leitura_serial()
	try:
		while True:
			time.sleep(1)
			print(obter_dado_serial())
	except KeyboardInterrupt:
		parar_leitura_serial()


if __name__ == "__main__":
	main()