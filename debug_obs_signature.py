"""
Script de diagnóstico de un solo uso: muestra la firma exacta (parámetros
aceptados) de los métodos relacionados con el formato de grabación en tu
versión instalada de obsws-python. Esto evita seguir adivinando nombres de
parámetros.

Uso:
    python debug_obs_signature.py
"""

import inspect

import obsws_python as obs

print("Versión de obsws-python:", getattr(obs, "__version__", "desconocida"))
print()

client_cls = obs.ReqClient

for method_name in ("get_profile_parameter", "set_profile_parameter"):
    method = getattr(client_cls, method_name, None)
    if method is None:
        print(f"⚠️  El método '{method_name}' no existe en esta versión.")
        continue
    try:
        sig = inspect.signature(method)
        print(f"{method_name}{sig}")
    except (TypeError, ValueError) as exc:
        print(f"No se pudo inspeccionar '{method_name}': {exc}")

print()
print("Si el resultado anterior no fue útil (por ejemplo, muestra solo *args, **kwargs),")
print("ejecuta también lo siguiente para ver el código fuente real del método:")
print()

import obsws_python.reqs as reqs_module
source_file = inspect.getsourcefile(reqs_module)
print("Archivo fuente:", source_file)

try:
    source = inspect.getsource(client_cls.get_profile_parameter)
    print("\n--- Código fuente de get_profile_parameter ---")
    print(source)
except Exception as exc:
    print(f"No se pudo obtener el código fuente: {exc}")
