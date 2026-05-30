import random, numpy as np, pandas as pd
from datetime import datetime, timedelta

NOMBRES  = ['Ana','Luis','María','Carlos','Patricia','Sofía','Jorge','Valentina','Miguel','Daniela','Andrés','Camila']
APELLIDOS= ['García','Martínez','López','Rodríguez','González','Pérez','Sánchez','Ramírez','Torres']
DIAGS    = ['Hipertensión','hipertencion','hipertensíon','Diabetes Tipo 2','Prehipertensión','Riesgo cardiovascular','Cardiopatía','Obesidad','Paciente sano']
SEXOS    = ['M','m','Masculino','F','f','Femenino']
ACTVS    = ['Sedentario','Baja','Media','Alta']
_counter = [9000]

class DataSimulator:
    def __init__(self, error_rate=0.08):
        self.error_rate = error_rate

    def generate(self, n=10) -> pd.DataFrame:
        records = [self._record() for _ in range(n)]
        df = pd.DataFrame(records)
        return self._inject_errors(df)

    def _record(self):
        _counter[0] += 1
        edad = random.randint(18, 90)
        peso = round(random.uniform(50, 110), 2)
        alt  = round(random.uniform(1.50, 1.95), 2)
        return {
            'id_paciente': _counter[0],
            'nombres': random.choice(NOMBRES), 'apellidos': random.choice(APELLIDOS),
            'edad': edad, 'sexo': random.choice(SEXOS),
            'peso': peso, 'altura': alt, 'IMC': round(peso/alt**2, 2),
            'presión_sistólica': random.randint(90,180),
            'presión_diastólica': random.randint(60,110),
            'frecuencia_cardiaca': random.randint(55,110),
            'glucosa': round(random.uniform(80,300),2),
            'colesterol': round(random.uniform(130,320),2),
            'saturación_oxígeno': round(random.uniform(88,99),2),
            'temperatura': round(random.uniform(36.0,39.5),1),
            'antecedentes_familiares': random.choice([True,False]),
            'fumador': random.choice([True,False]),
            'consumo_alcohol': random.choice([True,False]),
            'actividad_física': random.choice(ACTVS),
            'diagnóstico_preliminar': random.choice(DIAGS),
            'riesgo_enfermedad': 'Bajo',
            'fecha_consulta': (datetime(2025,1,1)+timedelta(days=random.randint(0,500))).strftime('%Y-%m-%d'),
        }

    def _inject_errors(self, df):
        n = len(df)
        err = lambda: random.sample(range(n), max(1, int(n*self.error_rate)))
        for col in ['peso','glucosa','colesterol','temperatura']:
            for i in err(): df.at[i, col] = None
        df['edad'] = df['edad'].astype(object)
        for i in err(): df.at[i,'edad'] = random.choice(['Treinta','N/A','Cuarenta'])
        df['presión_sistólica'] = df['presión_sistólica'].astype(object)
        for i in err(): df.at[i,'presión_sistólica'] = random.choice(['alta','baja'])
        if n >= 3:
            df.at[random.randint(0,n-1),'peso'] = 420.0
            # add one duplicate
            df = pd.concat([df, df.iloc[[0]]], ignore_index=True)
        return df
