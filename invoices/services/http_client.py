import os
import requests


def post_json(url, payload, headers=None, timeout=10):
    base_headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }
    if headers:
        base_headers.update(headers)

    try:
        response = requests.post(url, json=payload, headers=base_headers, timeout=timeout)
    except requests.RequestException as exc:
        raise RuntimeError(f"Erro de conexao ao chamar {url}: {exc}") from exc

    if response.status_code >= 400:
        raise RuntimeError(f"HTTP {response.status_code} ao chamar {url}: {response.text}")

    if not response.text:
        return {}
    return response.json()


def get_json(url, params=None, headers=None, timeout=10):
    base_headers = {
        'Accept': 'application/json',
    }
    if headers:
        base_headers.update(headers)

    try:
        response = requests.get(url, params=params, headers=base_headers, timeout=timeout)
    except requests.RequestException as exc:
        raise RuntimeError(f"Erro de conexao ao chamar {url}: {exc}") from exc

    if response.status_code >= 400:
        raise RuntimeError(f"HTTP {response.status_code} ao chamar {url}: {response.text}")

    if not response.text:
        return {}
    return response.json()
