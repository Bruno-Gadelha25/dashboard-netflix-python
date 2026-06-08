# Vitrine estática do Dashboard Netflix

Esta pasta contém uma versão estática do projeto criada para deploy na Vercel.
Ela funciona como uma apresentação visual do dashboard principal feito em
Streamlit.

## Conteúdo

- `index.html` com a narrativa do projeto
- capturas exportadas do dashboard em `assets/`
- links para o repositório GitHub

## Como publicar na Vercel

1. Entre nesta pasta:

```bash
cd vercel-static
```

2. Faça o deploy:

```bash
vercel
vercel --prod
```

## Observação

O dashboard interativo completo continua no arquivo `app.py` dentro da pasta
principal do projeto. A vitrine estática existe para facilitar o deploy em
ambiente compatível com Vercel.
