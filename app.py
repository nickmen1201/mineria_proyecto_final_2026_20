#Interfaz de despliegue: ¿se cancelará esta reserva? (Streamlit)
import datetime as dt

import streamlit as st

import utilidades_despliegue as u

st.set_page_config(page_title='¿Se cancelará esta reserva?', page_icon=':material/hotel:', layout='wide')

#Colores: estados (alto, moderado, bajo) y razones (rojo aumenta, azul reduce)
ESTADOS = {'alto': ('#d03b3b', 'Riesgo alto', 'Esta reserva probablemente se cancelará'),
           'moderado': ('#fab219', 'Riesgo moderado', 'Probablemente no se cancelará, pero hay señales de riesgo'),
           'bajo': ('#0ca30c', 'Riesgo bajo', 'Esta reserva probablemente no se cancelará')}
ROJO, AZUL, TINTA, TINTA_2, BORDE = '#e34948', '#2a78d6', '#0b0b0b', '#52514e', '#e7e6e2'

st.markdown(f"""
<style>
.block-container {{padding-top: 3rem; max-width: 1280px;}}
.encabezado {{background: #16324f; border-radius: 14px; padding: 22px 28px; margin-bottom: 1.2rem;}}
.encabezado h1 {{color: #ffffff; font-size: 1.7rem; margin: 0; padding: 0 !important; line-height: 1.3;}}
.encabezado p {{color: #c9d6e3; margin: 6px 0 0 0;}}
.tarjeta {{background: #ffffff; border: 1px solid {BORDE}; border-radius: 14px; padding: 20px 22px; margin-bottom: 14px;}}
.veredicto {{font-size: 1.6rem; font-weight: 700; color: {TINTA}; margin: 10px 0 2px 0; line-height: 1.3;}}
.estado {{display: inline-flex; align-items: center; gap: 8px; border: 1px solid {BORDE}; border-radius: 999px;
          padding: 3px 12px; font-weight: 600; color: {TINTA}; font-size: 0.9rem;}}
.punto {{width: 10px; height: 10px; border-radius: 50%; display: inline-block;}}
.medidor {{height: 10px; background: #f0efec; border-radius: 5px; margin: 8px 0 4px 0;}}
.medidor div {{height: 100%; border-radius: 5px;}}
.suave {{color: {TINTA_2}; font-size: 0.92rem;}}
.razon {{margin: 10px 0 0 0; color: {TINTA}; font-size: 0.95rem;}}
.barra {{height: 6px; border-radius: 3px; margin-top: 5px;}}
.subtitulo {{font-weight: 700; color: {TINTA}; margin: 0 0 4px 0;}}
.accion {{border-left: 4px solid #16324f; padding: 4px 0 4px 14px; margin: 12px 0;}}
.accion b {{color: {TINTA};}}
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def cargar_modelo():
    return u.cargar()


pipe, config = cargar_modelo()
cat, rng, opciones = config['categorias'], config['rangos'], config['opciones']
hoy = dt.date.today()
estado = st.session_state

#Valores iniciales del formulario (se guardan en la sesión para poder ajustarlos a las opciones válidas)
for clave, valor in {'hotel': 'City Hotel', 'fecha_reserva': hoy, 'fecha_llegada': hoy + dt.timedelta(days=60),
                     'adultos': 2, 'habitacion': 'A', 'parqueaderos': 0, 'solicitudes': 0, 'pais': 'PRT',
                     'cumplidas': 0, 'canceladas': 0, 'segmento': 'Online TA', 'canal': 'TA/TO', 'tipo': 'Transient',
                     'deposito': 'No Deposit', 'cambios': 0, 'espera': 0}.items():
    estado.setdefault(clave, valor)


def ajustar(clave, minimo=None, maximo=None, validas=None):
    """Si una respuesta deja de ser válida por otra (fechas, máximos u opciones), se corrige antes de mostrarla."""
    if validas is not None and estado[clave] not in validas:
        estado[clave] = validas[0]
    if minimo is not None and estado[clave] < minimo:
        estado[clave] = minimo
    if maximo is not None and estado[clave] > maximo:
        estado[clave] = maximo


def lista(clave, variable, texto, contenedor, valores=None, ayuda=None):
    valores = valores or cat[variable]
    ajustar(clave, validas=valores)
    return contenedor.selectbox(texto, valores, key=clave, help=ayuda, format_func=lambda v: u.etiqueta(variable, v))


st.markdown("""<div class="encabezado"><h1>¿Se cancelará esta reserva?</h1>
<p>Ingrese los datos de la reserva para saber si es probable que se cancele, por qué y qué hacer para evitarlo.
Hotel resort (Algarve) y hotel de ciudad (Lisboa).</p></div>""", unsafe_allow_html=True)

formulario, respuesta = st.columns([1.1, 1], gap='large')

#---------------------------------------------------------------- Datos de la reserva
with formulario:
    with st.container(border=True):
        st.markdown('**La estancia**')
        c1, c2 = st.columns(2)
        hotel = c1.radio('Hotel', cat['hotel'], key='hotel', format_func=lambda v: u.etiqueta('hotel', v))
        #fechas: la reserva ya se hizo (hasta hoy) y la llegada aún no ocurre, dentro de la anticipación observada
        ajustar('fecha_reserva', hoy - dt.timedelta(days=rng['lead_time'][1]), hoy)
        fecha_reserva = c2.date_input('Fecha en que se hizo la reserva', key='fecha_reserva', format='DD/MM/YYYY',
                                      min_value=hoy - dt.timedelta(days=rng['lead_time'][1]), max_value=hoy)
        llegada_min, llegada_max = max(hoy, fecha_reserva), fecha_reserva + dt.timedelta(days=rng['lead_time'][1])
        ajustar('fecha_llegada', llegada_min, llegada_max)
        fecha_llegada = c2.date_input('Fecha de llegada', key='fecha_llegada', format='DD/MM/YYYY',
                                      min_value=llegada_min, max_value=llegada_max)
        anticipacion = (fecha_llegada - fecha_reserva).days
        c1, c2, c3, c4 = st.columns(4)
        ajustar('adultos', 1, rng['adults'][1])
        adultos = c1.number_input('Adultos', 1, rng['adults'][1], key='adultos')
        ajustar('habitacion', validas=opciones['habitaciones'][hotel])
        habitacion = c2.selectbox('Habitación', opciones['habitaciones'][hotel], key='habitacion',
                                  format_func=lambda v: f'Tipo {v}',
                                  help='Código del tipo de habitación. Solo aparecen los tipos del hotel elegido.')
        maximo_parqueaderos = min(rng['required_car_parking_spaces'][1], adultos)
        ajustar('parqueaderos', 0, maximo_parqueaderos)
        parqueaderos = c3.number_input('Parqueaderos', 0, maximo_parqueaderos, key='parqueaderos',
                                       help='Como máximo uno por adulto.')
        solicitudes = c4.number_input('Solicitudes', *rng['total_of_special_requests'], key='solicitudes',
                                      help='Solicitudes especiales del cliente, por ejemplo cama doble o piso alto.')
        st.caption(f'Anticipación: {u.plural(anticipacion, "día", "días")}. Mes de llegada: '
                   f'{u.etiqueta("arrival_date_month", u.MESES[fecha_llegada.month - 1]).lower()}.')
    with st.container(border=True):
        st.markdown('**El cliente**')
        c1, c2, c3 = st.columns(3)
        pais = lista('pais', 'country', 'País de origen', c1)
        cumplidas = c2.number_input('Veces que se ha hospedado antes', *rng['previous_bookings_not_canceled'],
                                    key='cumplidas', help='Estancias anteriores del cliente en el hotel. 0 si es la '
                                                          'primera vez.')
        canceladas = c3.number_input('Reservas que ha cancelado antes', *rng['previous_cancellations'], key='canceladas')
    with st.container(border=True):
        st.markdown('**La reserva**')
        c1, c2 = st.columns(2)
        segmento = lista('segmento', 'market_segment', 'Origen de la reserva', c1)
        canal = lista('canal', 'distribution_channel', 'Canal de venta', c2, opciones['canales'][segmento],
                      'Solo aparecen los canales que se usan con el origen elegido.')
        c1, c2 = st.columns(2)
        tipo = lista('tipo', 'customer_type', 'Tipo de reserva', c1, ayuda='Individual: un cliente sin grupo ni '
                     'contrato. Ligada: individual pero asociada a otra reserva.')
        deposito = lista('deposito', 'deposit_type', 'Depósito', c2, ayuda='Sin depósito: no se pagó nada por '
                         'adelantado. No reembolsable: se pagó el valor total y no se devuelve si cancela. '
                         'Reembolsable: se pagó una parte que se devuelve si cancela.')
        c1, c2 = st.columns(2)
        cambios = c1.number_input('Cambios hechos a la reserva', *rng['booking_changes'], key='cambios')
        maximo_espera = min(rng['days_in_waiting_list'][1], anticipacion)
        ajustar('espera', 0, maximo_espera)
        espera = c2.number_input('Días en lista de espera', 0, maximo_espera, key='espera',
                                 help='No puede superar los días entre la reserva y la llegada.')
    evaluar = st.button('Evaluar reserva', type='primary', width='stretch', icon=':material/search:')


def tarjeta_acciones(lista_acciones):
    acciones = ''.join(f'<div class="accion"><b>{titulo}.</b> <span class="suave">{detalle}</span></div>'
                       for titulo, detalle in lista_acciones)
    st.markdown('#### ¿Qué hacer?')
    st.markdown(f'<div class="tarjeta">{acciones}</div>', unsafe_allow_html=True)


def bloque(titulo, filas, tono):
    items = ''.join(f'<p class="razon">{t}</p><div class="barra" style="width:{max(w, 0.06) * 100:.0f}%;'
                    f'background:{tono}"></div>' for t, w in zip(filas['texto'], filas['peso']))
    if not items:
        items = '<p class="razon suave">Ningún dato pesa de forma importante.</p>'
    return f'<div class="tarjeta"><p class="subtitulo">{titulo}</p>{items}</div>'


#---------------------------------------------------------------- Resultado
with respuesta:
    if not evaluar:
        st.markdown("""<div class="tarjeta"><p class="subtitulo">Cómo funciona</p>
            <p class="suave">Complete los datos de la reserva y presione <b>Evaluar reserva</b>. Obtendrá:</p>
            <p class="razon">1. Si la reserva probablemente se cancelará.</p>
            <p class="razon">2. Los datos de la reserva que más influyen en el resultado.</p>
            <p class="razon">3. Acciones sugeridas para evitar la cancelación.</p></div>""", unsafe_allow_html=True)
    else:
        datos = {'hotel': hotel, 'fecha_reserva': fecha_reserva, 'fecha_llegada': fecha_llegada, 'adultos': adultos,
                 'habitacion': habitacion, 'parqueaderos': parqueaderos, 'solicitudes': solicitudes, 'pais': pais,
                 'cumplidas': cumplidas, 'canceladas': canceladas, 'segmento': segmento, 'canal': canal,
                 'tipo': tipo, 'deposito': deposito, 'cambios': cambios, 'espera': espera}
        r = u.evaluar(datos, pipe, config, hoy)

        if r['tipo'] == 'incoherente':
            st.error('Revise los datos de la reserva:\n\n' + '\n'.join(f'{i}. {e}' for i, e in enumerate(r['errores'], 1)))

        elif r['tipo'] == 'sin_datos':
            #sin reservas históricas parecidas el modelo extrapola: no se da un veredicto
            revision = r['revision']
            motivos = ''.join(f'<p class="razon">{m}</p>' for m in revision['motivos'][:3])
            st.markdown(f"""<div class="tarjeta">
                <span class="estado"><span class="punto" style="background:#8a8984"></span>Sin datos suficientes</span>
                <div class="veredicto">No es posible estimar esta reserva con confianza</div>
                <p class="suave">Esta reserva no se parece a las reservas históricas con las que aprendió el modelo, así
                que su respuesta no sería confiable. Revise que los datos estén bien ingresados.</p>{motivos}</div>""",
                        unsafe_allow_html=True)
            if revision['perfil_raro']:
                guia = ''.join(f'<p class="razon">{i}. {texto} ({n:,} reservas).</p>'
                               for i, (texto, n) in enumerate(revision['parecidas'], 1))
                st.markdown(f'<div class="tarjeta"><p class="subtitulo">Combinaciones más comunes con '
                            f'{u.etiqueta("deposit_type", deposito).lower()}</p>{guia}</div>', unsafe_allow_html=True)
            tarjeta_acciones(r['sugerencias'])
            st.caption('Estas sugerencias se basan en las tasas históricas de cancelación de cada dato de la reserva, '
                       'no en una estimación del modelo.')

        else:
            color, etiqueta_estado, veredicto = ESTADOS[r['nivel']]
            st.markdown(f"""<div class="tarjeta">
                <span class="estado"><span class="punto" style="background:{color}"></span>{etiqueta_estado}</span>
                <div class="veredicto">{veredicto}</div>
                <p class="suave">Probabilidad estimada de cancelación: <b>{u.porcentaje(r['p'])}</b></p>
                <div class="medidor"><div style="width:{r['p'] * 100:.1f}%;background:{color}"></div></div>
                <p class="suave">Como referencia, de cada 100 reservas de estos hoteles se cancelan en promedio
                {config['tasa_cancelacion'] * 100:.0f}.</p></div>""", unsafe_allow_html=True)
            st.markdown('#### ¿Por qué?')
            c1, c2 = st.columns(2)
            c1.markdown(bloque('Hace más probable la cancelación', r['sube'], ROJO), unsafe_allow_html=True)
            c2.markdown(bloque('Hace menos probable la cancelación', r['baja'], AZUL), unsafe_allow_html=True)
            st.caption('La longitud de cada barra indica cuánto influye ese dato en el resultado.')
            tarjeta_acciones(r['sugerencias'])

st.caption(f'La estimación se basa en {config["registros"]:,} reservas de los dos hoteles con llegada entre julio de 2015 '
           'y agosto de 2017. Es un apoyo para decidir, no una certeza.')
