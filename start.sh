#!/bin/bash
echo "Ejecutando init_db.py..."
python init_db.py
echo "Iniciando gunicorn..."
exec gunicorn app:app
```
5. **Commit changes**

---

### **PASO 2: Modificar Procfile**

1. Abre el archivo **`Procfile`**
2. Edítalo y cambia a:
```
web: bash start.sh
