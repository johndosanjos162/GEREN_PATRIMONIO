# PMSC 2026 — Academia Militar Imersiva

Aplicação web de estudos para o concurso **PMSC 2026**, com ambiente **3D / WebXR** otimizado para **Meta Quest 3S**.

## Estrutura do projeto

```
pmsc-github/
├── index.html          # HTML — estrutura da página e do canvas 3D
├── css/
│   └── styles.css      # CSS — visual da interface 2D
├── js/
│   └── app.js          # JavaScript — Three.js, WebXR, lógica do app
└── README.md
```

### Trio web

| Arquivo | Papel |
|---------|--------|
| `index.html` | Estrutura: menus, `#scene` (canvas), botões |
| `css/styles.css` | Visual: cores, layout, tipografia |
| `js/app.js` | Lógica: cena 3D, VR, questões, tiro, áudio |

## Como rodar localmente

1. Sirva a pasta por HTTP (WebXR e módulos ES não funcionam bem em `file://`):

```bash
# Python
python -m http.server 8080

# ou Node
npx serve .
```

2. Abra `http://localhost:8080` no navegador.
3. No **Quest 3S**, abra a mesma URL no navegador do headset e toque em **ENTRAR EM VR**.

## GitHub Pages

1. Crie um repositório e envie esta pasta na raiz (ou em `/docs`).
2. Em **Settings → Pages**, escolha a branch `main` e a pasta `/ (root)`.
3. Acesse `https://github.com/johndosanjos162/PMSC`.

> **WebXR** exige **HTTPS** (GitHub Pages já fornece).

## Recursos

- Banco de questões (JSON no GitHub / importação local)
- Estudo, simulado, flashcards, revisões
- Ambientes 3D militares
- Painéis VR diegéticos
- Vinheta de conforto + ajuste de altura
- Áudio espacial
- Treino de tiro (alvos no VR — gatilho)

## Controles VR (Quest 3S)

- **Analógico esquerdo** — caminhar  
- **Analógico direito** — giro (snap)  
- **Gatilho** — selecionar UI / disparar no treino de tiro  
- **Grip / pinça** — arrastar painéis  
- **Círculos no piso** — teletransporte  

## Qualidade recomendada

No menu lateral: **Qualidade → Alta (Quest 3S)** e **Iluminação → Dia**.

## Licença

Uso educacional / pessoal para preparação PMSC.


## Atualização visual segura para Quest 3S (22/10/2026)

Esta versão mantém a estrutura e a lógica de estudos, simulados, flashcards,
locomoção e controles existentes. Alterações em `js/app.js`:

- O painel principal usa 2048×1536 em **Qualidade Alta**; as coordenadas
  da interface continuam 1536×1152 para preservar os cliques em botões.
- Adicionada filtragem com mipmaps e anisotropia nos painéis.
- Corrigidos contrastes no enunciado, notas e tela sem questões.
- Os dez ambientes do painel esquerdo cabem na área visível.
- Removido upload forçado de todas as texturas dos painéis em cada frame.
- A qualidade WebXR é configurada antes da sessão; removida a substituição
  involuntária da escala por 1,0.
- Solicitados **72 Hz** quando a API do navegador anuncia suporte; caso
  contrário, é mantida a taxa padrão do Quest.

**72 FPS é uma meta, não uma medição/garantia.** Verifique no headset antes
de decidir se deve reduzir a qualidade de Alta para Equilibrada. Se houver
painéis pretos ou perda de frames, selecione **Equilibrada** e reinicie o VR.
Mudar o fator de escala VR exige sair e entrar novamente no modo imersivo.

### Publicação

Faça backup dos arquivos atuais antes de substituir. Envie `index.html`,
`css/styles.css` e `js/app.js` preservando essas pastas no GitHub Pages.
Não apague os arquivos JSON de questões existentes no repositório.
