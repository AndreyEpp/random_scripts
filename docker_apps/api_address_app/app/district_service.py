import json
from dadata import Dadata
from decouple import config
import logging

token = config('TOKEN_DADATA')
secret = config('SECRET_DADATA')
dadata = Dadata(token, secret)

service_name = 'district_service'


def fetch_coordinates_dadata(address):
    '''
    https://dadata.ru/api/geocode/
    '''
    lon = None
    lat = None
    oktmo = None
    okato = None
    city_district = None
    found_places_json = None
    result = dadata.clean("address", address)
    address_clean = result['result']
    if address_clean is not None:
        lon = float(result['geo_lon'])
        lat = float(result['geo_lat'])
        oktmo = result['oktmo']
        okato = result['okato']
        city_district = result['city_district']
        found_places_json = json.dumps(result, ensure_ascii=False)

    return found_places_json, address_clean, lon, lat, oktmo, okato, city_district


def first_step(msql, address_living):
    # Добавляем новую запись
    need_update = False
    data_list = [
        address_living,
        need_update
    ]
    insert_list = [tuple(data_list)]
    insert_query = \
        """
        REPLACE INTO address_patients_logistic
        (
            address_living,
            need_update
        )
        VALUES (%s, %s)
        """
    # Вставляем запись
    try:
        msql.execute_many(insert_query, insert_list)
    except Exception as e:
        msql.send_log_bd(TypeError=e, service_name=service_name)
        logging.error(f'Не удалось вставить муниципальный район: {e}')
        # raise {'status_code': 400, 'text': e}


def second_step(msql, address_living):
    # ищем есть ли уже определенные координаты, если есть то забираем их, если нет, то ищем
    try:
        found_places_json, address_clean, lon, lat, oktmo, okato, city_district = fetch_coordinates_dadata(address_living)
        update_list = [found_places_json, address_clean, lon, lat, oktmo, okato, city_district]
        update_query = \
            f"""
            UPDATE address_patients_logistic
            SET found_places_json=%s, address_clean=%s,
            lon=%s, lat=%s, oktmo=%s, okato=%s, city_district=%s
            WHERE address_living='{address_living}'
            """
        msql.execute_query_arg(query=update_query, args=update_list)
        return oktmo
    except:
        update_list = [address_living]
        update_query = \
            f"""
            UPDATE address_patients_logistic
            SET not_found_address=1
            WHERE address_living='{address_living}'
            """
        try:
            msql.execute_query_arg(query=update_query, args=update_list)
        except Exception as e:
            msql.send_log_bd(TypeError=e, service_name=service_name)
            logging.error(f'Не удалось вставить муниципальный район: {e}')


def third_step(msql, oktmo, address_living):
    if oktmo is not None and address_living is not None:
        result = dadata.find_by_id("oktmo", oktmo[:8])
        if result:
            area = result[0]['data']['area']
            update_list = [area, address_living]
            update_query = \
                """
                UPDATE address_patients_logistic
                SET area=%s
                WHERE address_living=%s
                """
            try:
                msql.execute_query_arg(query=update_query, args=update_list)
            except Exception as e:
                msql.send_log_bd(TypeError=e, service_name=service_name)
                logging.error(f'Не удалось вставить муниципальный район: {e}')

            return area


def last_step(msql, address_living):
    update_query = \
        """
        UPDATE
        address_patients_logistic
        SET
        logistic_area =
        (SELECT okrug
        FROM raion_okrug_logistic
        WHERE raion_okrug_logistic.area=address_patients_logistic.area
       ) WHERE logistic_area is null
        """
    try:
        msql.execute_query_arg(query=update_query, args=None)
        select_query = \
            f"""
                SELECT logistic_area
                FROM address_patients_logistic
                WHERE address_living='{address_living}'
            """
        return msql.get_data_from_query(select_query)[0]

    except Exception as e:
        msql.send_log_bd(TypeError=e, service_name=service_name)
        logging.error(f'Не удалось обновить logistic_area: {e}')


def main(msql, address_living):
    first_step(msql, address_living)                   # Добавляем в БД
    oktmo = second_step(msql, address_living)          # Определяем координаты с помощью стороннего сервиса
    third_step(msql, oktmo, address_living)            # Получаем округ
    return last_step(msql, address_living)             # Получаем логистическое обозначение
