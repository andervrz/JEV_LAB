# Jev × CUAD

¿Puede un modelo localizar la cláusula que responde una pregunta contractual y abstenerse cuando los fragmentos disponibles son insuficientes? Este lab en Python evalúa a Jev con una muestra de diez casos anotados de CUAD sobre el preaviso para impedir una renovación automática. [API de TypeSafe](https://docs.typesafe.ai/api/system-one)

## Primera corrida real

En el contrato de Zounds, la cláusula anotada exige **60 días de preaviso por escrito**. Se hicieron dos peticiones a `jev-latest` desde Google Cloud Shell. La API devolvió `jev-1.14.0` en la corrida `ee00f96ee1474bc8892fabce0d6aca41`.

| Variante | Respuesta esperada | Respuesta de Jev | Suficiencia (0–2) |
| --- | --- | --- | ---: |
| Con la cláusula | `A` | `A` | 1,95 |
| Con tres distractores | `none` | `none` | 0,26 |

La diferencia fue **+1,69** (`1,95 − 0,26`). Hubo **1/1** aciertos de selección, **1/1** aciertos de abstención y cero fallos. Estas cifras corresponden a un solo par.

## Cómo se construye el par

1. La variante con evidencia incluye la cláusula anotada y dos distractores del mismo contrato.
2. En la otra variante, un tercer distractor ocupa la posición de la cláusula. La pregunta, los otros dos textos y las instrucciones son idénticos en ambas peticiones.
3. Jev elige `A`, `B`, `C` o `none` según si algún fragmento responde por sí solo. También puntúa por separado la suficiencia conjunta de los tres textos en una escala de 0 a 2.

La etiqueta esperada y la procedencia de los fragmentos se guardan en el registro local. Cada línea del JSONL conserva un intento con la petición, la respuesta y el modelo devuelto. El informe usa el último intento de cada variante para calcular métricas y muestra los fallos de todos los intentos.

## Uso

Necesitas Python 3.10 o posterior y `uv`. Clona el repositorio e instala el paquete.

```bash
git clone https://github.com/andervrz/JEV_LAB.git
cd JEV_LAB
uv sync
```

`preview` imprime el JSON que recibiría Jev. `report` reproduce el informe a partir de una corrida guardada. Ambos funcionan sin credenciales. El JSONL incluido en el repositorio es una **simulación** para probar el informe.

```bash
uv run jev-lab preview --case zounds-renewal-notice --condition without_evidence
uv run jev-lab report results/6e79a209e3464bb3be4811c2238224bc.jsonl
```

Para consultar la API, configura `TYPESAFE_API_KEY` en el entorno o en un archivo `.env` local. `run` imprime la ruta del JSONL.

```bash
run_file=$(uv run jev-lab run --case zounds-renewal-notice) &&
  uv run jev-lab report "$run_file"
```

Para ejecutar los diez casos de la muestra, usa `uv run jev-lab run --count 10`. La CLI usa `argparse` para los comandos y Rich para mostrar el informe.

### Pruebas

La suite usa transportes simulados para comprobar la construcción de las variantes, la validación de respuestas, el registro de intentos y las métricas.

```bash
uv sync --extra test
uv run --extra test pytest -q
```

## Datos y procedencia

La muestra proviene de **CUAD v1**, publicado por The Atticus Project bajo **CC BY 4.0**. El archivo original corresponde a la revisión `a3c393f5d103fd0c516374e4fdff676c8176dcb1`. [Copia en el repositorio](data/raw/CUAD_v1.json) · [Archivo en la revisión fijada](https://huggingface.co/datasets/theatticusproject/cuad/blob/a3c393f5d103fd0c516374e4fdff676c8176dcb1/CUAD_v1/CUAD_v1.json) · [Ficha y licencia](https://huggingface.co/datasets/theatticusproject/cuad)

Cada pregunta usa el texto del campo `Details` de CUAD. La evidencia y los tres distractores son extractos literales del mismo contrato. Sus títulos, índices de párrafo y posiciones iniciales permiten rastrear cada pasaje en la fuente. Los distractores se eligieron de cláusulas que, incluso juntas, dejan sin responder la pregunta de preaviso. [Muestra de diez casos](data/cases.json)
