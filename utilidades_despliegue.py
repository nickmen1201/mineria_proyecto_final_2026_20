#Funciones de apoyo de la interfaz: predicción, razones en lenguaje sencillo y sugerencias para evitar la cancelación
import json
import pickle

import pandas as pd
import xgboost as xgb

#Nombres en español de las categorías (los valores originales que recibe el modelo no cambian)
ETIQUETAS = {
    'hotel': {'City Hotel': 'Hotel de ciudad (Lisboa)', 'Resort Hotel': 'Hotel resort (Algarve)'},
    'arrival_date_month': {'January': 'Enero', 'February': 'Febrero', 'March': 'Marzo', 'April': 'Abril', 'May': 'Mayo',
                           'June': 'Junio', 'July': 'Julio', 'August': 'Agosto', 'September': 'Septiembre',
                           'October': 'Octubre', 'November': 'Noviembre', 'December': 'Diciembre'},
    'market_segment': {'Online TA': 'Agencia de viajes en línea', 'Offline TA/TO': 'Agencia u operador tradicional',
                       'Groups': 'Grupo', 'Direct': 'Directa con el hotel', 'Corporate': 'Empresa (corporativa)',
                       'Complementary': 'Cortesía del hotel', 'Aviation': 'Aerolínea'},
    'distribution_channel': {'TA/TO': 'Agencia u operador turístico', 'Direct': 'Directo con el hotel',
                             'Corporate': 'Convenio corporativo', 'GDS': 'Sistema global de reservas (GDS)'},
    'deposit_type': {'No Deposit': 'Sin depósito', 'Non Refund': 'Depósito no reembolsable',
                     'Refundable': 'Depósito reembolsable'},
    'customer_type': {'Transient': 'Individual', 'Transient-Party': 'Individual ligada a otra reserva',
                      'Group': 'Grupo', 'Contract': 'Contrato'},
    'country': {'PRT': 'Portugal', 'GBR': 'Reino Unido', 'FRA': 'Francia', 'ESP': 'España', 'DEU': 'Alemania',
                'ITA': 'Italia', 'IRL': 'Irlanda', 'BEL': 'Bélgica', 'BRA': 'Brasil', 'NLD': 'Países Bajos',
                'USA': 'Estados Unidos', 'CHE': 'Suiza', 'AUT': 'Austria', 'CN': 'China (CN)', 'CHN': 'China (CHN)',
                'SWE': 'Suecia', 'POL': 'Polonia', 'ISR': 'Israel', 'RUS': 'Rusia', 'NOR': 'Noruega',
                'Otros': 'Otro país'}}

MESES = list(ETIQUETAS['arrival_date_month'])  #orden del calendario
NOMBRES = {'hotel': 'Hotel', 'lead_time': 'Anticipación', 'arrival_date_month': 'Mes de llegada', 'adults': 'Adultos',
           'country': 'País', 'market_segment': 'Origen de la reserva', 'distribution_channel': 'Canal de venta',
           'is_repeated_guest': 'Huésped repetido', 'previous_cancellations': 'Reservas canceladas antes',
           'previous_bookings_not_canceled': 'Reservas cumplidas antes', 'reserved_room_type': 'Tipo de habitación',
           'booking_changes': 'Cambios a la reserva', 'deposit_type': 'Depósito',
           'days_in_waiting_list': 'Días en lista de espera', 'customer_type': 'Tipo de reserva',
           'required_car_parking_spaces': 'Parqueaderos', 'total_of_special_requests': 'Solicitudes especiales'}
MINIMO = 0.15  #aporte mínimo (escala del modelo) para mencionar una variable como razón


def cargar(ruta_modelo='modelo_hotel_bookings.pkl', ruta_config='despliegue_config.json'):
    pipe = pickle.load(open(ruta_modelo, 'rb'))
    config = json.load(open(ruta_config, encoding='utf-8'))
    return pipe, config


def etiqueta(variable, valor):
    return ETIQUETAS.get(variable, {}).get(str(valor), str(valor))


def plural(n, singular, varios):
    return f'{n} {singular if n == 1 else varios}'


def preparar(reservas, config):
    """Deja las reservas con las 17 variables, el orden y los tipos con los que se entrenó el Pipe."""
    X = reservas[config['variables']].copy()
    for variable in config['variables']:
        if variable in config['numericas']:
            X[variable] = pd.to_numeric(X[variable]).astype(int)
        else:
            X[variable] = X[variable].astype(str).str.strip()
    return X


def porcentaje(probabilidad):
    """Probabilidad para el usuario, sin mostrar 0% o 100% como si fueran certezas."""
    if probabilidad < 0.01:
        return 'menos de 1%'
    if probabilidad > 0.99:
        return 'más de 99%'
    return f'{probabilidad:.0%}'


def resultado(probabilidad, umbral):
    """Veredicto para el usuario: alto desde el umbral del modelo, moderado desde la mitad del umbral."""
    if probabilidad >= umbral:
        return 'alto'
    return 'moderado' if probabilidad >= umbral / 2 else 'bajo'


def aportes(pipe, X1):
    """Aporte de cada variable original a la predicción de una reserva (contribuciones de XGBoost)."""
    preparacion = pipe.named_steps['preparacion']
    Z = preparacion.transform(X1)
    valores = pipe.named_steps['modelo'].get_booster().predict(xgb.DMatrix(Z), pred_contribs=True)[0]
    columnas = [nombre.split('__', 1)[1] for nombre in preparacion.get_feature_names_out()]
    variables = list(X1.columns)
    suma = dict.fromkeys(variables, 0.0)
    for columna, valor in zip(columnas, valores[:-1]):
        #cada dummy se suma a su variable original (ej. deposit_type_Non Refund -> deposit_type)
        variable = max((v for v in variables if columna == v or columna.startswith(v + '_')), key=len)
        suma[variable] += float(valor)
    return pd.Series(suma).sort_values(key=abs, ascending=False)


def frase(variable, valor):
    """Describe en palabras el dato de la reserva que influye en el resultado."""
    v = valor
    if variable == 'lead_time':
        return f'Se reservó con {plural(v, "día", "días")} de anticipación'
    if variable == 'arrival_date_month':
        return f'La llegada es en {etiqueta(variable, v).lower()}'
    if variable == 'adults':
        return f'La reserva es para {plural(v, "adulto", "adultos")}'
    if variable == 'hotel':
        return f'Es una reserva en el {etiqueta(variable, v).split(" (")[0].lower()}'
    if variable == 'country':
        return 'El cliente es de un país con pocas reservas en el hotel' if v == 'Otros' else f'El cliente es de {etiqueta(variable, v)}'
    if variable == 'market_segment':
        return f'Origen de la reserva: {etiqueta(variable, v).lower()}'
    if variable == 'distribution_channel':
        return f'Se vendió por: {etiqueta(variable, v).lower()}'
    if variable == 'previous_cancellations':
        return 'El cliente no tiene cancelaciones anteriores' if v == 0 else f'El cliente ha cancelado {plural(v, "reserva", "reservas")} antes'
    if variable == 'historial':  #huésped repetido y reservas cumplidas, que el modelo usa en conjunto
        repetido, cumplidas = v
        if cumplidas > 0:
            return f'El cliente se ha hospedado {plural(cumplidas, "vez", "veces")} antes en el hotel'
        return 'Es la primera vez que el cliente se hospeda en el hotel'
    if variable == 'reserved_room_type':
        return f'Reservó una habitación tipo {v}'
    if variable == 'booking_changes':
        return 'La reserva no ha tenido cambios' if v == 0 else f'La reserva ha tenido {plural(v, "cambio", "cambios")}'
    if variable == 'deposit_type':
        return {'No Deposit': 'La reserva no tiene depósito', 'Non Refund': 'La reserva tiene un depósito no reembolsable',
                'Refundable': 'La reserva tiene un depósito reembolsable'}.get(v, f'Depósito: {v}')
    if variable == 'days_in_waiting_list':
        return 'La reserva no pasó por lista de espera' if v == 0 else f'La reserva estuvo {plural(v, "día", "días")} en lista de espera'
    if variable == 'customer_type':
        return f'Tipo de reserva: {etiqueta(variable, v).lower()}'
    if variable == 'required_car_parking_spaces':
        return 'No pidió parqueadero' if v == 0 else f'Pidió {plural(v, "parqueadero", "parqueaderos")}'
    return 'No tiene solicitudes especiales' if v == 0 else f'Tiene {plural(v, "solicitud especial", "solicitudes especiales")}'


def razones(aporte, X1):
    """Separa las razones que hacen más probable la cancelación de las que la hacen menos probable."""
    fila = X1.iloc[0].to_dict()
    #el historial del cliente se explica como un solo dato: huésped repetido + reservas cumplidas
    aporte = aporte.copy()
    aporte['historial'] = aporte.pop('is_repeated_guest') + aporte.pop('previous_bookings_not_canceled')
    fila['historial'] = (fila['is_repeated_guest'], fila['previous_bookings_not_canceled'])
    aporte = aporte.sort_values(key=abs, ascending=False)
    maximo = aporte.abs().max()
    tabla = pd.DataFrame({'variable': aporte.index, 'aporte': aporte.values})
    tabla = tabla[tabla['aporte'].abs() >= max(MINIMO, 0.1 * maximo)]  #solo los datos que pesan de verdad
    tabla['texto'] = [frase(v, fila[v]) for v in tabla['variable']]
    tabla['peso'] = tabla['aporte'].abs() / maximo  #intensidad relativa para la barra
    return tabla[tabla['aporte'] > 0].head(4), tabla[tabla['aporte'] < 0].head(4)


def sugerencias(aporte, X1, nivel):
    """Acciones para evitar la cancelación según lo que más pesa en esta reserva.
    Sin estimación del modelo (aporte=None) se usan solo los datos de la reserva y las tasas históricas."""
    if nivel == 'bajo':
        return [('Gestión normal', 'La reserva no muestra señales de cancelación que requieran acciones especiales. '
                 'Vuelva a evaluarla si el cliente la modifica.')]
    fila = X1.iloc[0]
    sube = set(X1.columns) if aporte is None else set(aporte[aporte >= MINIMO].index)
    lista = []
    if nivel == 'sin_datos':
        lista.append(('Reconfirmar la reserva', 'Como no hay reservas parecidas para estimar el riesgo, trátela con '
                      'precaución: confirme con el cliente o la agencia las fechas, el número de huéspedes y el depósito.'))
    if fila['deposit_type'] == 'Non Refund' and 'deposit_type' in sube:
        lista.append(('Verificar el depósito con la agencia', 'En los datos históricos se canceló el 99% de las reservas con '
                      'depósito no reembolsable. Casi todas eran bloques de habitaciones que agencias y operadores '
                      'reservaron para grupos y luego liberaron, no clientes que pagaron su estancia. Confirme con la '
                      'agencia que el pago se hizo y que las habitaciones tienen huéspedes asignados.'))
    if 'previous_cancellations' in sube and fila['previous_cancellations'] > 0:
        lista.append(('Pedir una garantía', 'El 92% de los clientes con cancelaciones anteriores volvió a '
                      'cancelar. Solicite una tarjeta de garantía o un '
                      'anticipo antes de bloquear la habitación.'))
    if 'lead_time' in sube and fila['lead_time'] >= 60:
        lista.append(('Mantener el contacto hasta la llegada', 'Las reservas hechas con más de 180 días de anticipación se '
                      'cancelan en el 57% de los casos, frente al 19% de las hechas con un mes o menos. Programe recordatorios y una reconfirmación una o dos '
                      'semanas antes.'))
    if 'total_of_special_requests' in sube and fila['total_of_special_requests'] == 0:
        lista.append(('Preguntar por sus preferencias', 'Las reservas con solicitudes especiales se cancelan menos (22% '
                      'frente a 48%). '
                      'Contacte al cliente para conocer qué necesita (tipo de cama, piso, celebraciones) y regístrelo.'))
    if 'required_car_parking_spaces' in sube and fila['required_car_parking_spaces'] == 0:
        lista.append(('Ofrecer parqueadero o traslado', 'En los datos, ninguna reserva con parqueadero se canceló. '
                      'Ofrezca '
                      'reservar parqueadero o un traslado desde el aeropuerto.'))
    if 'market_segment' in sube and fila['market_segment'] == 'Groups':
        lista.append(('Asegurar el grupo', 'El 61% de las reservas de grupo se canceló. Pida la lista de huéspedes y un anticipo, y acuerde una fecha límite para '
                      'liberar las habitaciones que el grupo no confirme.'))
    elif ('market_segment' in sube and fila['market_segment'] in ('Online TA', 'Offline TA/TO')) or \
            ('distribution_channel' in sube and fila['distribution_channel'] == 'TA/TO'):
        lista.append(('Crear relación directa con el cliente', 'Las reservas vendidas por agencias se cancelan más que las '
                      'directas (41% frente a 18%). Escriba al cliente para darle la bienvenida y confirmar su llegada.'))
    if 'days_in_waiting_list' in sube and fila['days_in_waiting_list'] > 0:
        lista.append(('Confirmar la reserva cuanto antes', 'Las reservas que pasaron por lista de espera se cancelan más '
                      '(64% frente a 36%). Avise al cliente que ya '
                      'está confirmada para que no busque otra opción.'))
    if nivel == 'alto':
        lista.append(('Prever la habitación en la sobreventa', 'Tenga en cuenta esta habitación al planear la ocupación '
                      'de esas fechas, por si finalmente se libera.'))
    if nivel == 'sin_datos':
        return lista[:4]
    if not lista:
        lista.append(('Recordar la reserva al cliente', 'Envíe un recordatorio con los detalles de la estancia una o dos '
                      'semanas antes de la llegada.'))
    return lista[:4]


def describir_perfil(clave):
    """Combinación de hotel, origen, canal, depósito y tipo de reserva en palabras."""
    hotel, segmento, canal, deposito, tipo = clave.split('|')
    return (f'{etiqueta("hotel", hotel).split(" (")[0].lower()}, origen {etiqueta("market_segment", segmento).lower()}, '
            f'canal {etiqueta("distribution_channel", canal).lower()}, {etiqueta("deposit_type", deposito).lower()} y '
            f'reserva {etiqueta("customer_type", tipo).lower()}')


#Tramos de las variables numéricas para contar reservas históricas parecidas en cada par de datos
CORTES = {'lead_time': [0, 7, 30, 90, 180, 365], 'adults': [0, 1, 2, 3, 4], 'previous_cancellations': [0, 1, 2],
          'previous_bookings_not_canceled': [0, 1, 2, 6], 'booking_changes': [0, 1, 2, 3],
          'days_in_waiting_list': [0, 1, 31, 91], 'required_car_parking_spaces': [0, 1],
          'total_of_special_requests': [0, 1, 2, 3]}
SIN_PARES = ['country', 'is_repeated_guest']  #el país fragmenta demasiado y huésped repetido se deduce del historial


def tramos(X):
    """Lleva cada reserva a tramos: categorías tal cual y números agrupados según CORTES."""
    T = pd.DataFrame(index=X.index)
    for variable in X.columns:
        if variable in SIN_PARES:
            continue
        if variable in CORTES:
            T[variable] = pd.cut(X[variable], CORTES[variable] + [10 ** 6], right=False, labels=False)
        else:
            T[variable] = X[variable]
    return T.astype(str)


def valor_legible(variable, valor):
    return f'{NOMBRES[variable].lower()}: {etiqueta(variable, valor).lower()}'


def confiabilidad(X1, config):
    """Revisa si la reserva se parece a reservas históricas: el modelo solo es confiable donde hay datos.
    Devuelve los motivos por los que no se puede estimar (lista vacía si la reserva tiene respaldo)."""
    fila = X1.iloc[0]
    minimo, minimo_par = config['minimo_reservas'], config['minimo_pares']
    motivos = []
    #1. categorías casi inexistentes
    for variable, conteo in config['conteo_categorias'].items():
        n = conteo.get(str(fila[variable]), 0)
        if n < minimo:
            motivos.append(f'Hay solo {n} reservas históricas con {valor_legible(variable, fila[variable])}.')
    #2. valores numéricos más altos que casi todo lo observado
    for variable in config['numericas']:
        if fila[variable] > config['limites'][variable]:
            motivos.append(f'Menos de {minimo} reservas históricas tienen {NOMBRES[variable].lower()} de '
                           f'{fila[variable]} o más.')
    #3. combinación de hotel, origen, canal, depósito y tipo de reserva
    clave = '|'.join(str(fila[v]) for v in config['perfil'])
    casos = config['perfiles'].get(clave, 0)
    if casos < minimo:
        motivos.append(f'Hay solo {casos} reservas históricas con esta combinación: {describir_perfil(clave)}.')
    #4. cada par de datos de la reserva
    T = tramos(X1).iloc[0]
    for par, conteo in config['pares'].items():
        a, b = par.split('|')
        n = conteo.get(f'{T[a]}|{T[b]}', 0)
        if n < minimo_par:
            motivos.append(f'Casi no hay reservas históricas con {valor_legible(a, fila[a])} y '
                           f'{valor_legible(b, fila[b])} ({n}).')
    #combinaciones reales más comunes con el mismo depósito, como guía cuando falla la combinación principal
    parecidas = sorted(((n, k) for k, n in config['perfiles'].items() if k.split('|')[3] == fila['deposit_type']),
                       reverse=True)[:2]
    return {'confiable': not motivos, 'motivos': motivos, 'casos': casos, 'perfil_raro': casos < minimo,
            'parecidas': [(describir_perfil(k), n) for n, k in parecidas]}


def revisar_coherencia(f, hoy):
    """Reglas lógicas entre los datos del formulario. Devuelve lo que el usuario debe corregir."""
    errores = []
    if f['fecha_reserva'] > hoy:
        errores.append('La fecha en que se hizo la reserva no puede ser posterior a hoy.')
    if f['fecha_llegada'] < hoy:
        errores.append('La fecha de llegada ya pasó: el modelo estima cancelaciones de reservas que aún no llegan.')
    if f['fecha_llegada'] < f['fecha_reserva']:
        errores.append('La fecha de llegada debe ser igual o posterior a la fecha en que se hizo la reserva.')
    anticipacion = max((f['fecha_llegada'] - f['fecha_reserva']).days, 0)
    if f['espera'] > anticipacion:
        errores.append(f'Los días en lista de espera ({f["espera"]}) no pueden superar los días entre la reserva y la '
                       f'llegada ({anticipacion}).')
    if f['adultos'] < 1:
        errores.append('La reserva debe tener al menos un adulto.')
    if f['parqueaderos'] > f['adultos']:
        errores.append('La reserva pide más parqueaderos que adultos.')
    if min(f['parqueaderos'], f['solicitudes'], f['cumplidas'], f['canceladas'], f['cambios'], f['espera']) < 0:
        errores.append('Los valores no pueden ser negativos.')
    return errores


def construir_reserva(f, config):
    """Pasa los datos del formulario a las 17 variables que recibe el Pipe."""
    reserva = pd.DataFrame([{
        'hotel': f['hotel'], 'lead_time': (f['fecha_llegada'] - f['fecha_reserva']).days,
        'arrival_date_month': MESES[f['fecha_llegada'].month - 1], 'adults': f['adultos'], 'country': f['pais'],
        'market_segment': f['segmento'], 'distribution_channel': f['canal'],
        'is_repeated_guest': '1' if f['cumplidas'] > 0 else '0',  #huésped repetido: se ha hospedado antes
        'previous_cancellations': f['canceladas'], 'previous_bookings_not_canceled': f['cumplidas'],
        'reserved_room_type': f['habitacion'], 'booking_changes': f['cambios'], 'deposit_type': f['deposito'],
        'days_in_waiting_list': f['espera'], 'customer_type': f['tipo'],
        'required_car_parking_spaces': f['parqueaderos'], 'total_of_special_requests': f['solicitudes']}])
    return preparar(reserva, config)


def evaluar(f, pipe, config, hoy):
    """Toda reserva recibe una de tres respuestas: datos incoherentes, sin datos suficientes o estimación."""
    errores = revisar_coherencia(f, hoy)
    if errores:
        return {'tipo': 'incoherente', 'errores': errores}
    X1 = construir_reserva(f, config)
    revision = confiabilidad(X1, config)
    if not revision['confiable']:
        return {'tipo': 'sin_datos', 'revision': revision, 'X': X1,
                'sugerencias': sugerencias(None, X1, 'sin_datos')}
    p = float(pipe.predict_proba(X1)[0, 1])
    nivel = resultado(p, config['umbral'])
    aporte = aportes(pipe, X1)
    sube, baja = razones(aporte, X1)
    return {'tipo': 'estimacion', 'p': p, 'nivel': nivel, 'sube': sube, 'baja': baja, 'X': X1,
            'sugerencias': sugerencias(aporte, X1, nivel)}
