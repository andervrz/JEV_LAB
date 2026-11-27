# Jev × CUAD · Instrucciones para Codex

## 1. Protocolo de construcción y revisión

Ander está aprendiendo a diseñar software. Mantén presente la arquitectura completa y desarrolla **un único módulo por iteración**. Si Ander pide arquitectura o una explicación, responde a ese nivel. Cuando pida comenzar la implementación, empieza por el módulo que indique o, en su defecto, por `cases.py`.

1. **Antes de escribir**, identifica el módulo, el problema que resuelve, sus entradas, su salida y un ejemplo verificable a mano. Explica por qué propones cada clase o función relevante. Hazlo brevemente en español.
2. **Implementa la pieza acordada.** Limita los cambios al módulo activo y a las pruebas o datos mínimos necesarios para comprobarlo. Representa servicios futuros con datos de prueba o una función simulada. Deja la creación de los demás módulos, incluidos sus esqueletos, para sus propias iteraciones.
3. **Entrega el módulo para lectura.** Indica los archivos modificados y el orden sugerido para leerlos. Recorre un ejemplo desde la entrada hasta la salida, explica una decisión de diseño y facilita el comando exacto para verificarlo. Distingue las pruebas ejecutadas, sus resultados y lo pendiente.
4. **Detente tras la entrega.** Espera a que Ander revise el código y autorice expresamente avanzar. Una pregunta abre una explicación; una corrección abre otra revisión del mismo módulo. Una prueba exitosa por sí sola no autoriza el siguiente. Si una modificación exige tocar otro módulo ya aprobado, explica el motivo y acuerda el alcance antes de editarlo.

## 2. Idioma y estilo de código

Escribe todo el código en inglés, incluidas las celdas de código del notebook. Usa inglés para módulos, clases, funciones, métodos, parámetros, variables, constantes, pruebas, campos JSON propios, opciones de CLI, mensajes, instrucciones del modelo y rúbricas. Usa `snake_case` para módulos, funciones y variables, `PascalCase` para clases y `UPPER_SNAKE_CASE` para constantes. Conserva los nombres del contrato externo de Jev y el texto original de CUAD.

Incluye comentarios en inglés donde ayuden a comprender una decisión o restricción. Por ejemplo: `# Keep the replacement in the same slot to control for position effects.` Escribe también en inglés las docstrings. Usa nombres descriptivos y funciones pequeñas. Justifica las clases por los datos o comportamientos que agrupan. Las explicaciones de diseño y revisión dirigidas a Ander van en español.

## 3. Qué se construye

Una herramienta Python para comprobar si Jev localiza la cláusula que responde una pregunta contractual y detecta cuándo la evidencia es insuficiente. La CLI con Rich permitirá previsualizar exactamente qué recibe el modelo, ejecutar uno o diez casos e inspeccionar una corrida guardada. El notebook de Kaggle reutilizará el paquete para explicar un caso, reproducir los resultados y graficar las diferencias. La vista previa y el informe funcionan sin red ni credenciales.

## 4. Datos y diseño del experimento

Usa CUAD v1 de The Atticus Project, revisión `a3c393f5d103fd0c516374e4fdff676c8176dcb1`, en `data/raw/CUAD_v1.json`. Registra procedencia, revisión, licencia y adaptaciones en el README. [Dataset](https://huggingface.co/datasets/theatticusproject/cuad)

Empieza con un caso revisado sobre el preaviso para impedir la renovación. Amplía la muestra a diez en `data/cases.json`. Cada `Case` contiene identificador, pregunta, fragmento anotado suficiente y tres distractores trazables. Verifica que los distractores, incluso juntos, dejan la pregunta sin responder.

Prepara dos objetos `Variant` por caso. En `with_evidence` presenta el fragmento correcto y dos distractores. En `without_evidence` sustituye el fragmento correcto por el tercer distractor en su misma posición. Distribuye reproduciblemente la posición correcta entre casos. En ambas variantes ofrece A, B, C y `none`. Mantén la etiqueta esperada, la condición y las anotaciones en el registro local. El modelo solo recibe la pregunta contractual y los tres textos visibles junto con las instrucciones de sus dos tareas.

## 5. Contrato con Jev

Envía una petición JSON por variante a `POST https://api.typesafe.ai/v1/systemone`, con autenticación Bearer y Content-Type application/json. El punto de entrada obtiene `TYPESAFE_API_KEY` del entorno y la pasa al cliente. Registra el modelo solicitado y el que devuelve la API. El modelo inicial es `jev-latest`.

Jev evalúa preguntas tipadas independientemente sobre un estado compartido. `choice` selecciona un fragmento. `score` mide la suficiencia del conjunto completo para contestar la pregunta contractual. La confianza de la elección y el score tienen significados distintos. Este ejemplo ficticio muestra el contrato de la petición:

```json
{
  "model": "jev-latest",
  "state": {
    "question": "How much advance notice is required to prevent renewal?",
    "passages": {
      "A": "Invoices are payable within 15 days.",
      "B": "Preventing automatic renewal requires 60 days' notice.",
      "C": "Early termination during the term requires 30 days' notice."
    }
  },
  "questions": {
    "passage": {
      "type": "choice",
      "instructions": "Select the passage that fully answers the question by itself.",
      "criteria": {"A": "Passage A", "B": "Passage B", "C": "Passage C", "none": "No passage fully answers the question"}
    },
    "sufficiency": {
      "type": "score",
      "instructions": "Rate the evidence across all passages for answering the question.",
      "criteria": ["No relevant evidence", "Relevant but incomplete evidence", "Both the notice period and its application to non-renewal are explicit"]
    }
  }
}
```

Lee `answers.passage.choice` y `answers.sufficiency.score`. Valida la opción y conserva el score decimal entre 0 y 2. Registra timeout, error HTTP o respuesta inválida como fallos diferenciados de una elección válida de `none`. [Documentación oficial](https://docs.typesafe.ai/introduction/quickstart)

## 6. Mapa de módulos y dependencias

Este orden guía la construcción. Cada fila corresponde a una entrega y su revisión.

| Orden | Pieza | Contrato y verificación |
|---|---|---|
| 1 | `src/jev_lab/cases.py` | Define `Case`, `Variant` y `build_pair`. De un caso obtiene dos variantes. Verifica que cambia un único fragmento y que ambas tienen tres opciones de texto. |
| 2 | `questions.py` | Construye la petición desde el modelo, la pregunta y los fragmentos visibles. Incluye la rúbrica y usa el mismo constructor para vista previa y ejecución. Verifica el JSON sin credenciales. |
| 3 | `client.py` | Envía la petición mediante `urllib.request` con timeout. Valida la respuesta, conserva el original y el uso de tokens cuando esté disponible. Prueba los caminos de éxito y fallo con transporte simulado. |
| 4 | `experiment.py` | Coordina variantes y función de consulta. Une cada intento con la referencia local y escribe un registro por intento en `results/`, en un JSONL por corrida. Comprueba primero un par con consulta simulada. |
| 5 | `evaluation.py` | Lee registros guardados y produce métricas y resultados por par. Prueba el ejemplo de aceptación de la sección 7 sin llamadas a Jev. |
| 6 | `cli.py` | Usa argparse y Rich para ofrecer `preview`, `run` y `report`. Delega construcción, ejecución y métricas a los módulos correspondientes. |
| 7 | `notebooks/cuad_jev.ipynb` | Carga la misma corrida que la CLI, reutiliza el evaluador y visualiza las diferencias por par con matplotlib. Revisión independiente después de aprobar la CLI. |

Declara las dependencias en pyproject.toml. Usa json, pathlib y dataclasses de la biblioteca estándar, python-dotenv para el entorno local y pytest para verificar el comportamiento. Implementa clases adicionales solo cuando puedas explicar la necesidad concreta.

## 7. Registro, métricas y aceptación

Conserva en JSONL el identificador de corrida, caso, variante e intento, la petición exacta, la etiqueta esperada local, el modelo devuelto, la respuesta y su estado. Incluye el uso de tokens cuando esté disponible. Excluye credenciales. Identifica las simulaciones. Los reintentos deben poder auditarse y cada variante cuenta una sola vez en el resumen.

- **Selección correcta**: aciertos sobre respuestas válidas con evidencia.
- **Abstención correcta**: elecciones de `none` sobre respuestas válidas sin evidencia.
- **Cambio por par**: `score_with - score_without`. Conserva resultados negativos y ceros. Muestra denominadores, fallos y pares incompletos.
- **Prueba verificable a mano**: si B es correcta con evidencia, Jev elige B en ambas variantes y los scores son 1,8 y 0,7, el resumen debe mostrar un acierto con evidencia, un error de abstención y una caída de 1,1.
- **Aceptación final**: CLI y notebook reproducen el mismo informe desde el mismo JSONL sin contactar la API. Describe por separado la evidencia obtenida con llamadas reales.
