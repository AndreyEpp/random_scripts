import MySQLdb
from datetime import datetime
from decouple import config


class MySQLClient:
    def __init__(self):
        try:
            self.db = MySQLdb.connect(host=config('DB_HOST'), port=int(config('DB_PORT')), user=config('DB_USER'),
                                      passwd=config('DB_PASS'), charset=config('DB_CHARSET'),
                                      db=config('DB_NAME'), ssl=config('DB_SSL'))
        except ValueError as e:
            raise f"Can't connect to database. {e}"

    def execute_query(self, query) -> None:
        with self.db.cursor() as cursor:
            cursor.execute(query)
            self.db.commit()

    def execute_query_arg(self, query: str, args) -> None:
        with self.db.cursor() as cursor:
            cursor.execute(query, args)
            self.db.commit()

    # todo Тест на доработку
    def execute_query_arg_v2(self, query: str, args):
        with self.db.cursor() as cursor:
            try:
                recount = cursor.execute(query, args)
                self.db.commit()
                return True
            except:
                return False

    def execute_many(self, insert_query, data_list: list):
        with self.db.cursor() as cursor:
            recount = cursor.executemany(insert_query, data_list)
            # cursor.executemany(insert_query, data_list)
            self.db.commit()
            return recount

    def get_data_from_query(self, query: str) -> list:
        with self.db.cursor() as cursor:
            recount = cursor.execute(query)
            return cursor.fetchall()

    def get_data_from_query2(self, query: str, args) -> list:
        with self.db.cursor() as cursor:
            recount = cursor.execute(query, args)
            return cursor.fetchall()

    def send_log_bd(self, TypeError, service_name):
        '''
        TypeError - получаемая ошибка в исходном виде Exception.
        Записываем ошибку в бд
        - время ошибки
        - тело ошибки
        - service_name
        '''

        time_error = str(datetime.now())[:19]
        body_error = TypeError

        data_list = [
            time_error,
            body_error,
            service_name
        ]
        insert_list = [tuple(data_list)]
        insert_query = \
            """
            REPLACE INTO api_logs
            (time_error, body_error, service_name
            )
            VALUES (%s, %s, %s)
            """
        # Вставляем запись
        self.execute_many(insert_query, insert_list)
        return True

    def close_connect(self):
        self.db.cursor().close()
        self.db.close()

# def dd(msql,address_living):
#     select_query = \
#         f"""
#                SELECT logistic_area
#                FROM address_patients_logistic
#                WHERE address_living='{address_living}'
#                """
#     logistic_area = msql.get_data_from_query(select_query)
#     print(0)
#
# if __name__ == "__main__":
#     msql = MySQLClient()
#     address_living = 'Москва, 2-ая Боевская, 6'
#     dd(msql, address_living)

