# 🌌 Dark Matter Lab

[![CI](https://github.com/USER/dark-matter-lab/actions/workflows/ci.yml/badge.svg)](https://github.com/USER/dark-matter-lab/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

Laboratório interativo para estudo de **matéria escura** via halos NFW/SIDM,
dinâmica estelar, feedback bariônico e simulações numéricas assíncronas.

![Screenshot](docs/SCREENSHOTS/tab_model.png)

## ✨ Funcionalidades

- **6 abas** cobrindo teoria, curvas de rotação, feedback e simulação
- **Assistente IA** em linguagem natural (PT/EN) que propaga parâmetros
- **Kernels Numba JIT** para física (perfil, integração, densidade) e integração
- **Arquitetura assíncrona** (Celery + Redis, com fallback ThreadPool local)
- **Relatório PDF** com síntese científica e gráficos Plotly via Kaleido
- **Spatial index** (KDTree adaptativo) para diagnósticos de vizinhança

## 🚀 Instalação rápida

```bash
git clone https://github.com/USER/dark-matter-lab.git
cd dark-matter-lab
pip install -r requirements.txt
streamlit run App.py
```

## 🐳 Docker (modo distribuído)

```bash
docker-compose up -d redis worker streamlit
# Acesse http://localhost:8501
```

## 📖 Documentação

- [Arquitetura](docs/ARCHITECTURE.md)
- [Parâmetros cosmológicos](docs/PARAMETERS.md)

## 🤝 Como contribuir

Veja [CONTRIBUTING.md](CONTRIBUTING.md).

## 📄 Licença

MIT — veja [LICENSE](LICENSE).
