# Jev × CUAD

El lab compara la selección de cláusulas y la suficiencia de la evidencia en dos variantes de cada pregunta contractual.

## CLI

Instala el paquete desde la raíz del proyecto.

```bash
python -m pip install -e '.[test]'
```

`preview` imprime la petición JSON. `report` lee una corrida guardada y muestra los resultados por caso.

```bash
jev-lab preview --case zounds-renewal-notice --condition without_evidence
jev-lab report results/6e79a209e3464bb3be4811c2238224bc.jsonl
```

`run` usa `TYPESAFE_API_KEY` del entorno o de un archivo `.env` local. Imprime la ruta del JSONL de la corrida.

```bash
jev-lab run --case zounds-renewal-notice
jev-lab run --count 10
```

## Datos

La muestra proviene de **CUAD v1**, publicado por The Atticus Project bajo **CC BY 4.0**. El archivo `data/raw/CUAD_v1.json` corresponde a la revisión `a3c393f5d103fd0c516374e4fdff676c8176dcb1`. [Archivo en la revisión fijada](https://huggingface.co/datasets/theatticusproject/cuad/blob/a3c393f5d103fd0c516374e4fdff676c8176dcb1/CUAD_v1/CUAD_v1.json) · [Licencia](https://huggingface.co/datasets/theatticusproject/cuad)

`data/cases.json` reúne diez contratos con una pregunta anotada sobre el preaviso de no renovación. Cada pregunta usa el texto del campo `Details` de CUAD. La evidencia y los tres distractores son extractos literales del mismo contrato, con título, índice de párrafo y posición inicial. Los distractores se eligieron de cláusulas que, incluso juntas, dejan sin responder la pregunta de preaviso.
