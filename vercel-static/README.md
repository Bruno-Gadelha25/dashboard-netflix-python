# Vitrine estática do Dashboard Netflix

Esta pasta contém uma versão estática do projeto criada para deploy na Vercel.
Ela serve diretamente a captura `netflix.png`, para que o endereço público
mostre exatamente a imagem do dashboard solicitada.

## Conteúdo

- `index.html` servindo a imagem principal
- `netflix.png` com a captura do dashboard

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
principal do projeto. A Vercel agora hospeda apenas a captura estática
solicitada.
