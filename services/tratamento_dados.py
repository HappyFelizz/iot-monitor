from __future__ import annotations

import re
from typing import Any


DISTANCIA_MIN_CM = 0.1
DISTANCIA_MAX_CM = 30.0
TEMPERATURA_HUMANO_MIN_C = 30.0


def _extrair_valor(texto: str, chave: str) -> float | None:
	"""Extrai valor flutuante após a chave no formato 'Chave: valor'."""
	padrao = rf"{re.escape(chave)}:\s*([\d.]+)"
	match = re.search(padrao, texto, re.IGNORECASE)
	return float(match.group(1)) if match else None


def _extrair_porta(texto: str) -> str | None:
	"""Extrai estado do portão (ABERTO/FECHADO)."""
	match = re.search(r"Portao:\s*(ABERTO|FECHADO)", texto, re.IGNORECASE)
	return match.group(1).upper() if match else None


def _detectar_humano(texto: str) -> bool:
	"""Detecta se há menção de 'Humano' no texto."""
	return bool(re.search(r"\bHumano\b", texto, re.IGNORECASE))


def _analisar_csv_legado(partes: list[str], texto_original: str = "") -> dict | None:
	"""Parser CSV legado (3-4 campos): angulo,distancia,temp_obj[,temp_amb]."""
	if len(partes) not in (3, 4):
		return None
	try:
		angulo = float(partes[0])
		distancia_cm = float(partes[1])
		temperatura_objeto_c = float(partes[2])
		if len(partes) == 4:
			temperatura_ambiente_c = float(partes[3])
		else:
			temperatura_ambiente_c = None
		distancia_valida = DISTANCIA_MIN_CM <= distancia_cm <= DISTANCIA_MAX_CM
		deteccao = "Humano" if _detectar_humano(texto_original) else None
		if deteccao is None:
			deteccao = "Humano" if temperatura_objeto_c >= TEMPERATURA_HUMANO_MIN_C else "Objeto"
		portao = _extrair_porta(texto_original) if texto_original else None
		
		return {
			"angulo": angulo,
			"distancia_cm": distancia_cm,
			"distancia_valida": distancia_valida,
			"faixa_distancia_cm": {
				"min": DISTANCIA_MIN_CM,
				"max": DISTANCIA_MAX_CM,
			},
			"temperatura_objeto_c": temperatura_objeto_c,
			"temperatura_ambiente_c": temperatura_ambiente_c,
			"deteccao": deteccao,
			"leitura_valida": distancia_valida,
			"portao": portao,
		}
	except ValueError:
		return None


def interpretar_linha(linha: str) -> Any:
	texto = linha.strip()
	if not texto:
		return None

	if "|" in texto:
		angulo = _extrair_valor(texto, "Angulo")
		distancia_cm = _extrair_valor(texto, "Distancia")
		temperatura_c = _extrair_valor(texto, "Temp")
		portao = _extrair_porta(texto)

		if angulo is not None and distancia_cm is not None and temperatura_c is not None:
			distancia_valida = DISTANCIA_MIN_CM <= distancia_cm <= DISTANCIA_MAX_CM
			deteccao = "Humano" if _detectar_humano(texto) else ("Humano" if temperatura_c >= TEMPERATURA_HUMANO_MIN_C else "Objeto")
			return {
				"angulo": angulo,
				"distancia_cm": distancia_cm,
				"distancia_valida": distancia_valida,
				"faixa_distancia_cm": {
					"min": DISTANCIA_MIN_CM,
					"max": DISTANCIA_MAX_CM,
				},
				"temperatura_objeto_c": temperatura_c,
				"temperatura_ambiente_c": None,
				"deteccao": deteccao,
				"leitura_valida": distancia_valida,
				"portao": portao,
			}

	partes = [parte.strip() for parte in texto.split(",")]
	resultado = _analisar_csv_legado(partes, texto)
	if resultado is not None:
		return resultado

	return texto


def tratar_erro_serial(erro: Exception) -> str:
	return f"{type(erro).__name__}: {erro}"