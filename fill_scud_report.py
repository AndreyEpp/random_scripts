'''
Создание - 07.07.2023 Андрей.
Последнее обновление - ..2023 Андрей.
'''
import mayak_help_lib
from datetime import timedelta
import datetime
import pytz
import json
import importlib.resources as pkg_resources


class ScudReport:
    DATE_REPORT_ID = 10
    DAY_WEEK_ID = 20
    EMPLOYMENT_TYPE_ID = 13
    START_TIME_ID = 11
    FINISH_TIME_ID = 12
    ROAD_TIME_ID = 28
    TOTAL_TIME_ID = 26
    LINK_TASK_ID = 19
    COMMENTS_ID = 12
    PATIENT_ID = 21

    def __init__(self, data=None, task_body=None):
        self.msql = mayak_help_lib.MySQLClient()
        self.data = data
        self.task_body = task_body
        self.update_table_row_all, self.update_hot_line_table_row_all = [], []
        self.update_table_row_all2 = {}
        self.field_updates = []

        self.update_overtime_table_row_all, self.overtime_new_row = [], 0
        self.overtime, self.pre_overtime, self.dop_pay = 0, 0, ''
        self.overtime_plus, self.overtime_minus = 0, 0
        self.update_error_entrance_table_row_all, self.error_entrance_new_row = [], 0
        self.update_dezhurstvo_table_row_all, self.dezhur_row_id = [], 0
        self.task_ids_dezhurstva_stc = []
        self.night_st_duty_week, self.day_st_duty_week, self.night_st_duty_weekend, self.day_st_duty_weekend = 0, 0, 0, 0
        self.day_st_duty_holiday, self.night_st_duty_holiday = 0, 0

        self.work_day_must_be = 0
        self.amount_working_day, self.average_duration, self.total_duration, self.total_duration2 = 0, 0, 0, 0
        self.vacation_regular, self.vacation_at_your_own, self.day_off, self.sick_day = 0, 0, 0, 0
        self.range_vr, self.range_vyo, self.range_do, self.range_sd = [], [], [], []

        self.night_duty, self.day_duty = 0, 0
        self.texting, self.calling, self.visits = 0, 0, 0
        self.ip_post = 0

        self.exepts = [80431690, 80431603, 80431677]
        self.employee = self.task_body['employee_id']
        self.department = self.task_body['department']
        self.lunch_time = self.get_pd()
        self.type_team = self.checking_dep()
        self.schema = self.get_schema()
        self.reply = self.fill_report()

    def checking_dep(self):
        # Фактическое деление на отдел.
        departments = self.data.session.get_catalog_reply(121480).json()
        # Бэк-офис
        dp_office_id = [
            item['item_id'] for item in departments.get('items') if item['values'][2] != 'Выездная служба'
            and item['values'][2] != 'Стационарное отделение' and item['values'][2] != 'Проект по сопровождаемому проживанию'
            and item['values'][2] != 'Респираторная служба']
        if self.department in dp_office_id:
            return 'back_office'

        return 'visiting_service'

    def get_pd(self):
        pd_task = self.data.session.get_register_filtered_reply(
            form_id=802538,
            archived='n',
            search=f'fld14={self.employee}&field_ids=78'
        ).json().get('tasks', [])
        if pd_task:
            try:
                return pd_task[0]['fields'][0]['value']
            except:
                pass
        return 1

    def get_schema(self):
        schema = pkg_resources.open_binary(mayak_help_lib.scud, 'schema_scud_report.json')
        # schema = pkg_resources.open_binary('schema_scud_report.json')
        schema = json.load(schema)
        return schema[self.type_team]

    def fill_report(self):
        # Формирование диапазона отпусков отгулов больничных
        def range_days_off(days_off):
            range_date = ''
            if isinstance(days_off[0], list):
                range_date = {}
                for rd in days_off:
                    range_date[f"{rd[0].strftime('%d.%m.%Y')} - {rd[1].strftime('%d.%m.%Y')}"] = f'({(rd[1] - rd[0]).days + 1})'
                cv = [f'{i} - {range_date.get(i)}' for i in range_date]
                range_date = '\n'.join(cv)
            else:
                dates = [datetime.datetime.strptime(e_d, '%Y-%m-%d') for e_d in days_off]
                previous_start, previous_end = dates[0], dates[len(dates)-1]
                if len(dates) == 1:
                    range_date += f"{dates[0].date().strftime('%d.%m.%Y')} (1)\n"
                elif len(dates) == 2:
                    for start, end in zip(dates, dates[1:len(dates)]):
                        if (end - start).days == 1:
                            range_date += f"{previous_start.date().strftime('%d.%m.%Y')} - {end.date().strftime('%d.%m.%Y')} ({(end - previous_start).days + 1})\n"
                        else:
                            range_date += f"{start.date().strftime('%d.%m.%Y')} (1)\n{end.date().strftime('%d.%m.%Y')} (1)"
                else:
                    for start, end in zip(dates, dates[1:len(dates)]):
                        if (end - start).days == 1:
                            previous_end = end
                            continue
                        else:
                            previous_end = start
                            range_date += f"{previous_start.date().strftime('%d.%m.%Y')} - {previous_end.date().strftime('%d.%m.%Y')} ({(previous_end - previous_start).days + 1})\n"
                            previous_start = end
                    previous_end = end
                    range_date += f"{previous_start.date().strftime('%d.%m.%Y')} - {previous_end.date().strftime('%d.%m.%Y')} ({(previous_end - previous_start).days + 1})\n"

            return range_date

        def daterange(start_date, end_date):
            for n in range(int((end_date - start_date).days)):
                yield start_date + timedelta(n)

        def time_interval_v2(one_day_list):
            all_day_reset = False   # Обнулять весь день если больничный
            reset_ids = []          # ID строк которые обнуляем
            rest_time_ids = {}
            o_w = []
            list_delete = []

            all_times = []
            all_dates = []

            one_day_list = sorted(one_day_list, key=lambda d: [d['day_st']], reverse=False)
            for row in one_day_list:
                if row.get('cells', None) is None:
                    continue
                plain_row = {
                    cell['id']: cell['value'] for cell in row['cells']
                }
                current_date = plain_row.get(10)
                all_dates.append(current_date)

                change_row_id = row.get('row_id')
                if plain_row.get(13) is not None:
                    if plain_row.get(13)['item_id'] == 107648489:   # Скуд в выходной обнуляем
                        if grafik_flag is True and rday in holidays or rday in weekends:
                            reset_ids.append(change_row_id)
                            continue
                    if plain_row.get(13)['item_id'] == 106664199:   # Обучение обнуляем
                        reset_ids.append(change_row_id)
                        continue

                # https://pyrus.com/t#id195103553 Журавлева отработала отгул 25/12 за 22/12
                if plain_row.get(25) is not None and plain_row.get(25).find('Отработка в свой нерабочий день ранее предоставленный отгул') != -1:
                    all_day_reset = True
                    break

                if plain_row.get(25) is not None:
                    if plain_row.get(25).find('Работа сверх установленного рабочего графика (по производственной необходимости)') != -1\
                            or plain_row.get(25).find('Отработка в свой нерабочий день перенесенное рабочее время') != -1:
                        o_w.append(change_row_id)
                        continue

                if plain_row.get(11) is not None and plain_row.get(12) is not None:
                    time_start = datetime.datetime.strptime(plain_row.get(11)[:5], '%H:%M').time()
                    time_finish = datetime.datetime.strptime(plain_row.get(12)[:5], '%H:%M').time()
                    commuting = 0
                    if plain_row.get(28) is not None:
                        commuting = plain_row.get(28) / 60

                    all_times.append({'time_start': time_start, 'time_finish': time_finish, 'row_id': change_row_id})

                    if all_times:
                        for slot in all_times:
                            if slot.get('row_id') == change_row_id:
                                continue

                            if slot.get('time_start') <= time_start <= slot.get('time_finish') and time_finish <= slot.get('time_finish'):
                                if len(set(all_dates)) == 1:
                                    reset_ids.append(change_row_id)
                                if self.task_body.get('lead_Lida'):
                                    list_delete.append(change_row_id)

                            elif slot.get('time_finish') >= time_start <= slot.get('time_start') < time_finish <= slot.get('time_finish'):
                                amount = timedelta(hours=time_finish.hour, minutes=time_finish.minute) - \
                                         timedelta(hours=slot.get('time_finish').hour, minutes=slot.get('time_finish').minute)
                                # Проверяем если уже у это строки было пересечение и если было оставляем то, где меньше часов
                                if rest_time_ids.get(change_row_id) is not None:
                                    if amount / 3600 < rest_time_ids.get(change_row_id):
                                        rest_time_ids[change_row_id] = amount.seconds / 3600 + commuting
                                else:
                                    rest_time_ids[change_row_id] = amount.seconds / 3600 + commuting
                            elif slot.get('time_start') <= time_start <= slot.get('time_finish') >= time_finish:
                                amount = timedelta(hours=time_start.hour, minutes=time_start.minute) - \
                                         timedelta(hours=slot.get('time_finish').hour,
                                                   minutes=slot.get('time_finish').minute)
                                if rest_time_ids.get(change_row_id) is not None:
                                    if amount / 3600 < rest_time_ids.get(change_row_id):
                                        rest_time_ids[change_row_id] = amount.seconds / 3600 + commuting
                                else:
                                    rest_time_ids[change_row_id] = amount.seconds / 3600 + commuting
                            elif slot.get('time_start') <= time_start < slot.get('time_finish') <= time_finish:
                                amount = timedelta(hours=time_finish.hour, minutes=time_finish.minute) - \
                                         timedelta(hours=slot.get('time_finish').hour,
                                                   minutes=slot.get('time_finish').minute)
                                if rest_time_ids.get(change_row_id) is not None:
                                    if amount.seconds / 3600 < rest_time_ids.get(change_row_id):
                                        rest_time_ids[change_row_id] = amount.seconds / 3600 + commuting
                                else:
                                    rest_time_ids[change_row_id] = amount.seconds / 3600 + commuting
            if all_day_reset:
                reset_ids = []
                for row in one_day_list:
                    if row.get('cells', None) is None:
                        continue
                    reset_ids.append(row.get('row_id'))
                rest_time_ids = []
                return reset_ids, rest_time_ids, o_w, list_delete
            return reset_ids, rest_time_ids, o_w, list_delete

        def overtime_count(one_day_list, norma_den):
            start_time, extra_text = '', ''
            all_times = []
            over_work_schedule, over_event_work = False, False
            ows, oew = 0, 0
            for act in one_day_list:
                # Если есть Работа сверх установленного рабочего графика / отпуск / отгул (отключил)  / больничный - удаляем т.к. не считаем переработку
                cells = act.get('cells')
                if cells is not None:
                    # Павел 22.12
                    # needs = [act['row_id'] for u in act.get('cells')
                    #          if (u['id'] == 13 and u['value'].get('item_id') in types_activity_off[1:]) or
                    #          (u['id'] == 10 and u['value'] in weekends or u['value'] in holidays)]

                    needs = [act['row_id'] for u in act.get('cells')
                             if (u['id'] == 13 and u['value'].get('item_id') in types_activity_off[1:])]
                    needs_weekends_holidays = [act['row_id'] for u in act.get('cells')
                             if (u['id'] == 10 and u['value'] in weekends or u['value'] in holidays)]

                    over_work_schedule = [act['row_id'] for u in act.get('cells') if u['id'] == 25 and
                                          (u['value'].find('Работа сверх установленного рабочего графика') != -1 or
                                          u['value'].find('Отработка в свой нерабочий день перенесенное рабочее время') != -1)]
                    # Удаляем из таблицы переработки Отработка в свой нерабочий день
                    over_event_work = needs.extend([act['row_id'] for u in act.get('cells') if u['id'] == 25 and
                                       u['value'].find(
                                           'Отработка в свой нерабочий день ранее предоставленный отгул') != -1])

                    if needs:
                        continue

                    over_work_hour = [i.get('value') for i in cells if i.get('id') == 26]
                    if over_work_hour:
                        if over_work_schedule:
                            ows += sum(over_work_hour)
                        elif over_event_work:
                            oew += sum(over_work_hour)
                        else:
                            all_times.extend(over_work_hour)

            if all_times or ows > 0 or oew > 0:
                amount = sum(all_times)
                if over_work_schedule:
                    reason_dayoff = 'Переработка рабочего времени: Работа сверх установленного рабочего графика (по производственной необходимости)'
                    overtime = ows
                elif over_event_work:
                    reason_dayoff = 'Переработка рабочего времени: Отработка в свой нерабочий день ранее предоставленный отгул'
                    overtime = oew
                elif amount > norma_den:
                    reason_dayoff = f'Переработка рабочего времени'
                    overtime = amount - norma_den
                elif amount < norma_den:
                    reason_dayoff = 'Недоработка рабочего времени'
                    overtime = amount - norma_den
                else:
                    return
                overtime_cell_updates = []
                overtime_cell_updates.append({'id': 89, 'value': overtime})
                overtime_cell_updates.append({'id': 90, 'value': rday})
                overtime_cell_updates.append({'id': 92, 'value': reason_dayoff})

                update_table_row = {'row_id': self.overtime_new_row, 'cells': overtime_cell_updates,
                                    'day_st': rday + start_time}

                self.overtime_new_row += 1
                self.update_overtime_table_row_all.append(update_table_row)
                self.overtime += overtime
                if overtime > 0:
                    self.overtime_plus += overtime
                else:
                    self.overtime_minus += overtime

        def get_data_from_bd(wd, rday, previous_day, row_id):
            change_date_status = False
            any_other_act_day, is_it_sick_day = False, False
            not_empty_day = 0
            new_row = row_id
            check_many_dates = []
            self.update_table_row_all_list = []
            for bd in self.schema:
                data_scud = {}
                schema_query = f'{self.schema.get(bd).get("query")}'                      # Схема запроса в БД
                schema_response = self.schema.get(bd).get("schema_response")              # Схема выборки данных из БД
                select_query = schema_query.format(rday=rday, employee_id=self.employee)  # Подставляем данные
                tasks_scud = list(self.msql.get_data_from_query(select_query))
                # self.msql.cursor.close()
                for each_task in tasks_scud:
                    ip_post_flag = False
                    cells_updates = []
                    for i, k in enumerate(schema_response):
                        response = {k: each_task[i]}
                        data_scud.update(response)

                    if bd == 'form_961352_hotline':
                        any_other_act_day = True
                        check_many_dates.append(rday)
                        finish_time_UTC_time, start_time_UTC_time = None, None
                        start_time, finish_time = "00:00", "00:00"
                        if data_scud.get('start_time') is not None:
                            start_time_UTC_time = datetime.datetime.strptime(data_scud.get('start_time')[:5],
                                                                             TIME_PYRUS_FORMAT).replace(tzinfo=UTC_TZ)
                            start_time = start_time_UTC_time.strftime(TIME_PYRUS_FORMAT)
                            cells_updates.append({'id': 42, 'value': start_time})
                        if data_scud.get('finish_time') is not None:
                            finish_time_UTC_time = datetime.datetime.strptime(data_scud.get('finish_time')[:5],
                                                    TIME_PYRUS_FORMAT).replace(tzinfo=UTC_TZ)
                            finish_time = finish_time_UTC_time.strftime(TIME_PYRUS_FORMAT)
                            cells_updates.append({'id': 43, 'value': finish_time})

                        amount = 0
                        if start_time_UTC_time is not None and finish_time_UTC_time is not None:
                            amount = (finish_time_UTC_time - start_time_UTC_time).seconds / 3600

                        if data_scud.get('finish_date') is not None:
                            cells_updates.append({'id': 47, 'value': str(data_scud.get('finish_date'))[:11]})

                        cells_updates.append({'id': 44, 'value': amount})
                        cells_updates.append({'id': 41, 'value': rday})

                        update_table_row = {'row_id': new_row, 'cells': cells_updates, 'day_st': rday + start_time}

                        new_row += 1
                        self.update_hot_line_table_row_all.append(update_table_row)

                        if start_time < finish_time:
                            self.day_duty += 1
                        else:
                            self.night_duty += 1

                    elif (bd == 'form_776405_events' or bd == 'form_fundraising') and data_scud.get('conditions') is not None:
                        # Считаем как рабочий
                        # 1. Рабочий день по графику - переносится время в отчет в верхнюю таблицу 152501722 -
                        # НЕ считаем как рабочий, но берем часы в нижнюю таблицу часы переработки:
                        # 2. Работа сверх графика с последующим отгулом 152501723 -
                        # 3. Работа сверх графика с последующим уменьшением часов других рабочих дней 152501724
                        # 4. Работа сверх графика с дополнительной оплатой часов - берем часы в поле
                        # id114 "Участие в мероприятии за дополнительную оплату" 152501725
                        # если не заполнено поле условия учета (conditions), то берем как 1 вариант
                        reason_dayoff = ''
                        if int(data_scud.get('conditions')) == 152501723:
                            reason_dayoff = 'Работа сверх графика с последующим отгулом'
                        elif int(data_scud.get('conditions')) == 152501724:
                            reason_dayoff = 'Работа сверх графика с последующим уменьшением часов других рабочих дней'

                        if data_scud.get('start_time') is not None:
                            start_time_UTC_time = datetime.datetime.strptime(data_scud.get('start_time')[:5],
                                                                             TIME_PYRUS_FORMAT).replace(
                                tzinfo=UTC_TZ)
                        if data_scud.get('finish_time') is not None:
                            finish_time_UTC_time = datetime.datetime.strptime(data_scud.get('finish_time')[:5],
                                                                              TIME_PYRUS_FORMAT).replace(
                                tzinfo=UTC_TZ)

                        if start_time_UTC_time is not None and finish_time_UTC_time is not None:
                            overtime = ((finish_time_UTC_time + timedelta(hours=3)) - (start_time_UTC_time + timedelta(hours=3))).seconds / 3600

                            if int(data_scud.get('conditions')) in [152501723, 152501724]:

                                overtime_cell_updates = []
                                overtime_cell_updates.append({'id': 89, 'value': overtime})
                                overtime_cell_updates.append({'id': 90, 'value': rday})
                                overtime_cell_updates.append({'id': 92, 'value': reason_dayoff + ' ' + f'https://pyrus.com/t#id{data_scud.get("task_id")}'})

                                update_table_row = {'row_id': self.overtime_new_row, 'cells': overtime_cell_updates,
                                                    'day_st': rday + data_scud.get('start_time')}

                                self.overtime_new_row += 1
                                self.update_overtime_table_row_all.append(update_table_row)
                                self.overtime += overtime
                                if overtime > 0:
                                    self.overtime_plus += overtime
                                else:
                                    self.overtime_minus += overtime

                            else:
                                # int(data_scud.get('conditions')) == 152501725:
                                # reason_dayoff = 'Работа сверх графика с дополнительной оплатой часов'
                                self.dop_pay += f'https://pyrus.com/t#id{data_scud.get("task_id")} - {overtime}\n'
                    else:
                        check_many_dates.append(rday)
                        if data_scud.get('visit_date') is not None:
                            visit_date = str(data_scud.get('visit_date'))[:10]
                            if visit_date != rday and bd == 'all_visits_view_nanny':
                                change_date_status = True
                                change_date = visit_date
                                if wd == 6:
                                    wd = 0
                                else:
                                    wd += 1

                        pk = data_scud.get('pk')
                        if pk is not None:
                            cells_updates.append({'id': 34, 'value': f"{data_scud.get('pk')}/{rday}"})
                        else:
                            cells_updates.append({'id': 34, 'value': f"{data_scud.get('task_id')}/{rday}"})

                        if data_scud.get('task_id') is not None:
                            if type(data_scud.get('task_id')) is int:
                                cells_updates.append({'id': 19, 'value': f"https://pyrus.com/t#id{data_scud.get('task_id')}"})
                            else:
                                xy = [f"https://pyrus.com/t#id{i}" for i in map(int, data_scud.get('task_id').split('\n'))]
                                cells_updates.append({'id': 19, 'value': '\n'.join(xy)})
                        if data_scud.get('employment') is not None and data_scud.get('employment') != 0:
                            if data_scud.get('employment') == 'Переписка':
                                self.texting += 1
                                continue
                            elif data_scud.get('employment') == 'Звонок':
                                self.calling += 1
                                continue
                            elif data_scud.get('employment') == 'Встреча' or data_scud.get('employment') == 'Встреча в рамках беривмент программы':
                                cells_updates.append({'id': 13, 'value': {'item_id': 106664198}})
                            else:
                                if int(data_scud.get('employment')) == 106664191 and data_scud.get('form_id') == 768473:
                                    continue
                                cells_updates.append({'id': 13, 'value': {'item_id': int(data_scud.get('employment'))}})
                                if int(data_scud.get('employment')) == 106664227:
                                    self.vacation_regular += 1
                                    self.range_vr.append([data_scud.get('start_date'), data_scud.get('finish_date')])
                                elif int(data_scud.get('employment')) == 106664228:
                                    self.vacation_at_your_own += 1
                                    self.range_vyo.append([data_scud.get('start_date'), data_scud.get('finish_date')])
                                elif int(data_scud.get('employment')) == 106664219:
                                    self.day_off += 1
                                    self.range_do.append(rday)
                                elif int(data_scud.get('employment')) == 106664229:
                                    is_it_sick_day = True
                                    self.sick_day += 1
                                    self.range_sd.append([data_scud.get('start_date'), data_scud.get('finish_date')])
                                elif int(data_scud.get('employment')) == 106664190:
                                    self.visits += 1
                                elif int(data_scud.get('employment')) == 106664203:
                                    ip_post_flag = True

                        type_a = ''
                        if data_scud.get('type_activity') is not None and data_scud.get('comment') is not None:
                            type_a += f"{data_scud.get('type_activity')} / {data_scud.get('comment')}"
                        elif data_scud.get('type_activity') is not None:
                            type_a += f"{data_scud.get('type_activity')}"
                        # elif data_scud.get('type_activity') is None and data_scud.get('comment') is not None:
                        #     type_a += f"{data_scud.get('comment')}"
                        elif data_scud.get('comment') is not None:
                            type_a += f" /{data_scud.get('comment')}"

                        if data_scud.get('program') is not None:
                            type_a += f" / {data_scud.get('program')}"

                        if data_scud.get('patient_id') is not None:
                            if type(data_scud.get('patient_id')) is int:
                                # Если пациент не на учете и для разовой консультации врача педиатра
                                if data_scud.get('patient_id') == 999999999:
                                    pass
                                else:
                                    cells_updates.append({'id': 21, 'value': {'item_id': data_scud.get('patient_id')}})
                            else:
                                to_int = map(int, data_scud.get('patient_id').split(','))
                                cells_updates.append({'id': 21, 'value': {'item_ids': list(to_int)}})

                        start_date = data_scud.get('start_date')
                        finish_date = data_scud.get('finish_date')

                        finish_time_UTC_time, start_time_UTC_time = None, None
                        start_time = '00:00'
                        if data_scud.get('start_time') is not None and data_scud.get('start_time')[:5] != '25:00' and\
                                data_scud.get('start_time') != '':
                            # if bd == 'scud_report' or bd == 'all_visits_view_with_apartaments':
                            if bd == 'scud_report':
                                start_time_UTC_time = datetime.datetime.strptime(data_scud.get('start_time')[:5],
                                                                                 TIME_PYRUS_FORMAT) + timedelta(hours=-3)
                                start_time = start_time_UTC_time.strftime(TIME_PYRUS_FORMAT)
                            elif bd in ['form_913966_duty', 'form_961352_hotline', 'all_visits_view_nanny']:
                                start_time_UTC_time = datetime.datetime.strptime(data_scud.get('start_time')[:5],
                                                                                 TIME_PYRUS_FORMAT).replace(tzinfo=UTC_TZ)
                                start_time = start_time_UTC_time.strftime(TIME_PYRUS_FORMAT)
                                if start_time == '00:00':
                                    start_time = '21:00'
                            else:
                                start_time_UTC_time = datetime.datetime.strptime(data_scud.get('start_time')[:5],
                                                                                 TIME_PYRUS_FORMAT)
                                start_time = start_time_UTC_time.strftime(TIME_PYRUS_FORMAT)
                            cells_updates.append({'id': 11, 'value': start_time})
                        if data_scud.get('finish_time') is not None and data_scud.get('finish_time')[:5] != '-25:0' and \
                                data_scud.get('finish_time') != '':
                            # if bd == 'scud_report' or bd == 'all_visits_view_with_apartaments':
                            if bd == 'scud_report':
                                finish_time_UTC_time = datetime.datetime.strptime(data_scud.get('finish_time')[:5],
                                                                                  TIME_PYRUS_FORMAT) + timedelta(hours=-3)
                                finish_time = finish_time_UTC_time.strftime(TIME_PYRUS_FORMAT)
                            elif bd in ['form_913966_duty', 'all_visits_view_nanny']:
                                finish_time_UTC_time = datetime.datetime.strptime(data_scud.get('finish_time')[:5],
                                                                                 TIME_PYRUS_FORMAT).replace(tzinfo=UTC_TZ)
                                finish_time = finish_time_UTC_time.strftime(TIME_PYRUS_FORMAT)
                                if finish_time == '00:00':
                                    finish_time = '21:00'
                            else:
                                finish_time_UTC_time = datetime.datetime.strptime(data_scud.get('finish_time')[:5],
                                                                                      TIME_PYRUS_FORMAT)
                                finish_time = finish_time_UTC_time.strftime(TIME_PYRUS_FORMAT)
                            cells_updates.append({'id': 12, 'value': finish_time})

                        amount = 0
                        if start_time_UTC_time is not None and finish_time_UTC_time is not None:
                            if bd == 'form_913966_duty':
                                if start_time_UTC_time.strftime('%H:%M') == '00:00':
                                    amount = ((finish_time_UTC_time + timedelta(hours=3)) - start_time_UTC_time).seconds / 3600
                                elif finish_time_UTC_time.strftime('%H:%M') == '00:00':
                                    amount = ((finish_time_UTC_time + timedelta(
                                        hours=-3)) - start_time_UTC_time).seconds / 3600
                                else:
                                    amount = (finish_time_UTC_time - start_time_UTC_time).seconds / 3600

                                if data_scud.get('task_id') not in self.task_ids_dezhurstva_stc:
                                    self.task_ids_dezhurstva_stc.append(data_scud.get('task_id'))
                                    select_query = \
                                        f"""
                                        SELECT min(date_work) as start_day, max(date_work) as finish_date, max(start_time) as start_time, max(finish_time) as finish_time
                                        FROM form_913966_duty
                                        WHERE task_id={data_scud.get('task_id')}
                                        """

                                    tasks_duty = self.msql.get_data_from_query(select_query)
                                    st_date_d = tasks_duty[0][0]
                                    fn_date_d = tasks_duty[0][1]
                                    st_d_t = tasks_duty[0][2]
                                    fn_d_t = tasks_duty[0][3]

                                    if st_date_d.month != fn_date_d.month:
                                        st_date_d = fn_date_d
                                        st_d_t = '21:00'

                                    new_dif = \
                                        (datetime.datetime.strptime(fn_d_t, TIME_PYRUS_FORMAT).replace(tzinfo=UTC_TZ)
                                         - datetime.datetime.strptime(st_d_t, TIME_PYRUS_FORMAT).replace(tzinfo=UTC_TZ)).seconds / 3600

                                    if st_date_d == fn_date_d:
                                        if rday in weekends:
                                            self.day_st_duty_weekend += new_dif
                                        elif rday in holidays:
                                            self.day_st_duty_holiday += new_dif
                                        else:
                                            self.day_st_duty_week += new_dif
                                    else:
                                        if rday in weekends:
                                            self.night_st_duty_weekend += new_dif
                                        elif rday in holidays:
                                            self.night_st_duty_holiday += new_dif
                                        else:
                                            self.night_st_duty_week += new_dif

                                    dezhurstvo_cell_updates = []
                                    dezhurstvo_cell_updates.append({'id': 67, 'value': str(st_date_d)})
                                    dezhurstvo_cell_updates.append({'id': 68, 'value': st_d_t})
                                    dezhurstvo_cell_updates.append({'id': 69, 'value': str(fn_date_d)})
                                    dezhurstvo_cell_updates.append({'id': 70, 'value': fn_d_t})
                                    dezhurstvo_cell_updates.append({'id': 71, 'value': new_dif})

                                    update_table_row = {'row_id': self.dezhur_row_id, 'cells': dezhurstvo_cell_updates,
                                                        'day_st': rday + start_time}

                                    self.dezhur_row_id += 1
                                    self.update_dezhurstvo_table_row_all.append(update_table_row)

                            elif bd == 'all_visits_view_nanny':
                                if start_time_UTC_time.strftime('%H:%M') == '00:00':
                                    amount = ((finish_time_UTC_time + timedelta(hours=3)) - start_time_UTC_time).seconds / 3600
                                elif finish_time_UTC_time.strftime('%H:%M') == '00:00':
                                    amount = (finish_time_UTC_time - (start_time_UTC_time + timedelta(hours=3))).seconds / 3600
                                else:
                                    amount = (finish_time_UTC_time - start_time_UTC_time).seconds / 3600

                            # elif bd == 'form_894245_activity':
                            #     if data_scud.get('overtime') != 1:
                            #         amount = (finish_time_UTC_time - start_time_UTC_time).seconds / 3600
                            #         if amount > 8:
                            #             amount = amount - 1
                            else:
                                if start_date is not None and finish_date is not None:
                                    finish_time_UTC_time = datetime.datetime.strptime(data_scud.get('finish_time')[:5],
                                                TIME_PYRUS_FORMAT).replace(tzinfo=UTC_TZ) + timedelta(days=1)

                                if start_time > finish_time:
                                    amount = 0
                                else:
                                    amount = (finish_time_UTC_time - start_time_UTC_time).seconds / 3600
                                # Вычитаем время на обед у всех (размер в пд) и
                                # врачи стационара - только у Морозовой, Киселева, Серегиной, но если это не дежурство
                                if (amount > 5 and self.employee not in self.exepts) or \
                                   (amount > 5 and self.employee in self.exepts and int(data_scud.get('employment')) != 106664197):
                                    amount = amount - self.lunch_time

                        elif data_scud.get('employment') is not None and data_scud.get('type_activity') is None:
                            if start_time_UTC_time is None and finish_time_UTC_time is not None:
                                type_time = 1
                            elif finish_time_UTC_time is None and start_time_UTC_time is not None:
                                type_time = 2
                            else:
                                type_time = 3

                            if self.type_team == 'back_office' and rday not in weekends and rday not in holidays:
                                if int(data_scud.get('employment')) not in types_activity_off and \
                                   int(data_scud.get('employment')) not in [106664189, 106664208, 106664199]:
                                    type_a += f"Нет данных входа/выхода"

                                    if type_time != 3:
                                        error_entrance_updates = []
                                        error_entrance_updates.append({'id': 101, 'value': rday})
                                        error_entrance_updates.append({'id': 102, 'value': {'choice_id': type_time}})
                                        st_t = data_scud.get('start_time')
                                        if len(st_t) == 0 or st_t is None:
                                            st_t = '25:00'
                                        ft_t = data_scud.get('finish_time')
                                        if len(ft_t) == 0 or ft_t is None:
                                            ft_t = '-25:00'
                                        pk_k = f"{self.employee}/{rday}/{st_t}/{ft_t}"
                                        error_entrance_updates.append({'id': 111, 'value': pk_k})
                                        update_table_row = {'row_id': self.error_entrance_new_row,
                                                            'cells': error_entrance_updates,
                                                            'day_st': rday + start_time}

                                        self.error_entrance_new_row += 1
                                        self.update_error_entrance_table_row_all.append(update_table_row)
                            elif self.type_team == 'visiting_service' and (start_time_UTC_time is None or finish_time_UTC_time is None):
                                type_a += f"Нет данных входа/выхода"

                                if type_time != 3:
                                    error_entrance_updates = []
                                    error_entrance_updates.append({'id': 101, 'value': rday})
                                    error_entrance_updates.append({'id': 102, 'value': {'choice_id': type_time}})

                                    st_t = data_scud.get('start_time')
                                    if len(st_t) == 0 or st_t is None:
                                        st_t = '25:00'
                                    ft_t = data_scud.get('finish_time')
                                    if len(ft_t) == 0 or ft_t is None:
                                        ft_t = '-25:00'
                                    pk_k = f"{self.employee}/{rday}/{st_t}/{ft_t}"
                                    error_entrance_updates.append({'id': 111, 'value': pk_k})

                                    update_table_row = {'row_id': self.error_entrance_new_row,
                                                        'cells': error_entrance_updates,
                                                        'day_st': rday + start_time}

                                    self.error_entrance_new_row += 1
                                    self.update_error_entrance_table_row_all.append(update_table_row)
                        else:
                            if data_scud.get('employment') is None:
                                cells_updates.append({'id': 13, 'value': {'item_id': 106664233}})

                        if data_scud.get('commuting') is not None and data_scud.get('type_activity') != 'Работа сверх установленного рабочего графика (по производственной необходимости)':
                            if bd == 'form_907281_otgul':
                                amount += data_scud.get('commuting')
                            else:
                                try:
                                    commuting = int(data_scud.get('commuting'))
                                except:
                                    commuting = 0

                                if commuting > 0:
                                    amount += commuting / 60
                                cells_updates.append({'id': 28, 'value': commuting})

                        if data_scud.get('duration') is not None:
                            duration = 0
                            if bd != 'form_1003711_feedback':
                                duration = float(data_scud.get('duration', 0))
                            os_time = float(data_scud.get('os_time', 0))
                            break_time = float(data_scud.get('break_time', 0))
                            amount += ((duration * 60) + os_time + break_time) / 60

                        if data_scud.get('diary_time') is not None:
                            if data_scud.get('diary_time') > 0:
                                amount += data_scud.get('diary_time') / 60
                                cells_updates.append({'id': 95, 'value': data_scud.get('diary_time')})

                        if data_scud.get('km') is not None:
                            cells_updates.append({'id': 98, 'value': data_scud.get('km')})

                        if ip_post_flag:
                            if start_time_UTC_time is not None and finish_time_UTC_time is not None:
                                if start_time_UTC_time.strftime('%H:%M') == '00:00' or (start_time_UTC_time.strftime('%H:%M') != '00:00'
                                                                      and finish_time_UTC_time.strftime('%H:%M') != '00:00'):
                                    self.ip_post += 1

                        # За отмененные визиты по умлочанию 90 минут https://pyrus.com/t#id190200030
                        if data_scud.get('employment') == 106664192:
                            amount += 90 / 60

                        not_empty_day += 1
                        cells_updates.append({'id': 26, 'value': amount})
                        cells_updates.append({'id': 25, 'value': type_a})
                        cells_updates.append({'id': 20, 'value': week[wd]})

                        if change_date_status:
                            cells_updates.append({'id': 10, 'value': change_date})
                        else:
                            cells_updates.append({'id': 10, 'value': rday})

                        update_table_row = {'row_id': new_row,
                                            'cells': cells_updates, 'day_st': rday + start_time}

                        new_row += 1
                        self.update_table_row_all.append(update_table_row)
                        self.update_table_row_all_list.append(update_table_row)

                        try:
                            if int(data_scud.get('employment')) != 106664229:
                                any_other_act_day = True
                        except:
                            pass

                        # Подсчет раб. часов:
                        # дата != предыдущей дате, ни выходной, ни праздник, ни любой тип отпуска/отгула
                        if rday != previous_day:
                            previous_day = rday

                            if (rday in holidays or rday in weekends) and self.type_team == 'back_office':
                                pass
                            else:
                                if data_scud.get('employment') in ['Переписка', 'Звонок', 'Встреча', 'Встреча в рамках беривмент программы']:
                                    self.amount_working_day += 1
                                elif int(data_scud.get('employment')) not in types_activity_off[1:]:
                                    if amount > 0 or int(data_scud.get('employment')) == 107648489:
                                        self.amount_working_day += 1

                            if rday not in holidays and rday not in weekends:
                                try:
                                    if int(data_scud.get('employment')) not in types_activity_off[1:]:
                                        self.work_day_must_be += 1
                                except:
                                    if data_scud.get('employment') in ['Переписка', 'Звонок', 'Встреча', 'Встреча в рамках беривмент программы']:
                                        self.work_day_must_be += 1

            # Если за один день помимо больничного был еще скуд или другие активности - вычитаем 1
            if is_it_sick_day and any_other_act_day:
                self.amount_working_day -= 1
                self.work_day_must_be -= 1
            # Если нет данных по дню и он попадает в праздники или сб/вск - заполняем выходной день
            if not_empty_day == 0 and (rday in weekends or rday in holidays):
                cells_updates = []
                check_many_dates.append(rday)
                cells_updates.append({'id': 13, 'value': {'item_id': 106664233}})
                cells_updates.append({'id': 20, 'value': week[wd]})
                cells_updates.append({'id': 10, 'value': rday})
                cells_updates.append({'id': 34, 'value': f'{rday}/{week[wd]}'})

                update_table_row = {'row_id': new_row,
                                    'cells': cells_updates, 'day_st': rday + '00:00'}

                new_row += 1
                self.update_table_row_all.append(update_table_row)
                self.update_table_row_all_list.append(update_table_row)

            # Если нет данных по дню - заполняем неопределенно
            elif not_empty_day == 0:
                cells_updates = []
                check_many_dates.append(rday)
                cells_updates.append({'id': 13, 'value': {'item_id': 107391575}})
                cells_updates.append({'id': 20, 'value': week[wd]})
                cells_updates.append({'id': 10, 'value': rday})
                cells_updates.append({'id': 34, 'value': f'{rday}/{week[wd]}'})

                self.work_day_must_be += 1
                update_table_row = {'row_id': new_row,
                                    'cells': cells_updates, 'day_st': rday + '00:00'}

                new_row += 1
                self.update_table_row_all.append(update_table_row)
                self.update_table_row_all_list.append(update_table_row)

            for rday in set(check_many_dates):
                self.update_table_row_all2.update({rday: self.update_table_row_all_list})
            return 200

        TIME_PYRUS_FORMAT = '%H:%M'
        UTC_TZ = pytz.timezone('UTC')

        week = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']
        # значения справочника Праздничные и выходные дни
        catalog = self.data.session.get_catalog_reply(176256).json().get('items')

        holidays = []   # Праздничные дни
        holidays_bad_type = [item['values'][0] for item in catalog if item['values'][1] == 'holidays']
        for day in holidays_bad_type:
            holidays.append(f'{day[6:10]}-{day[3:5]}-{day[:2]}')

        weekends = []   # Выходные дни
        weekends_bad_type = [item['values'][0] for item in catalog if item['values'][1] == 'weekends']
        for day in weekends_bad_type:
            weekends.append(f'{day[6:10]}-{day[3:5]}-{day[:2]}')

        # Отгул / Отпуск очередной (оплачиваемый) / Отпуск за свой счет (неоплачиваемый)/ Больничный
        types_activity_off = [106664219, 106664227, 106664228, 106664229]

        if self.task_body.get('year_report') is not None and self.task_body.get('month_report') is not None:
            start_date = datetime.date(self.task_body.get('year_report'), self.task_body.get('month_report'), 1)
            end_date = datetime.date(self.task_body.get('year_report'), self.task_body.get('month_report'),
                                     self.task_body.get('amount_calendar_days')) + timedelta(days=1)
            step = 3
        else:
            start_date = datetime.date(int(self.task_body.get('first_day_report')[:4]), int(self.task_body.get('first_day_report')[5:7]),
                                       int(self.task_body.get('first_day_report')[8:]))
            end_date = datetime.date(int(self.task_body.get('last_day_report')[:4]), int(self.task_body.get('last_day_report')[5:7]),
                                     int(self.task_body.get('last_day_report')[8:])) + timedelta(days=1)
            step = 2

        # Если дата отчета > последний день месяц - статус на проверку
        # if datetime.date.today() >= end_date:
        #     self.field_updates.append({'id': 24, 'value': {'choice_id': 2}})

        # Ставка
        stavka_flag = True
        try:
            if isinstance(self.task_body.get('stavka'), str):
                stavka = float(self.task_body.get('stavka').replace(',', '.'))
            else:
                stavka = float(self.task_body.get('stavka'))
            if stavka < 1:
                stavka_flag = False
            elif stavka > 1:
                stavka = 1
        except:
            stavka_flag = False
            stavka = 1

        # Рабочий график берет число часов в день, оно существует только для 5/2
        if self.task_body.get('grafik') is not None:
            grafik = float(self.task_body.get('grafik'))
            grafik_flag = True
        else:
            grafik = 8
            grafik_flag = False

        norma_den = grafik * stavka     # Норма часов в день учитывая ставку

        previous_day = None
        row_id = 0

        all_list_delete, list_reset, dict_minus = [], [], {}

        for rday in daterange(start_date, end_date):
            wd = rday.weekday()     # День недели
            rday = str(rday)[:10]   # Дата

            get_data_from_bd(wd, rday, previous_day, row_id)

            day_list = self.update_table_row_all2.get(rday)
            row_id += len(day_list)

            # функция обработки пересечений временных отрезков
            l_r, l_m, o_w = [], [], []
            # Павел 22.12 добавил =
            if len(day_list) >= 1:
                l_r, l_m, o_w, l_d = time_interval_v2(day_list)
                list_reset.extend(l_r)
                dict_minus.update(l_m)
                all_list_delete.extend(l_d)

            # Обнуляем или корректируем строки пересекающихся диапазонов
            for x in l_r:
                for y in day_list:
                    if y['row_id'] == x:
                        day_list.remove(y)
            for x in l_m:
                for y in day_list:
                    if y['row_id'] == x:

                        index = -1
                        for i in y['cells']:
                            index += 1
                            if i['id'] == 26:
                                break

                        y['cells'][index] = {'id': 26, 'value': l_m.get(x)}

            # Предпраздничный день. Если да, то норма дня будет на час меньше
            koef_pre_holiday = 0
            pre_holiday = str(datetime.datetime.strptime(rday, '%Y-%m-%d') + timedelta(days=1))[:10]
            if pre_holiday in holidays:
                koef_pre_holiday = 1

            # Переработки считаем если место работы кроме Выездная и Квартиры, известна ставка и она >= 1, есть график работы 5/2
            if self.task_body.get('place_work') not in [105796850, 105975377, None] and grafik_flag is True and stavka_flag is True:
                overtime_count(day_list, norma_den - koef_pre_holiday)

            # Обнуляем сверхурочный график в главной таблице
            for x in o_w:
                for y in day_list:
                    if y['row_id'] == x:
                        index = -1
                        for i in y['cells']:
                            index += 1
                            if i['id'] == 26:
                                break

                        y['cells'][index] = {'id': 26, 'value': 0}

            # Считаем количество часов
            all_times = []
            for act in day_list:
                cells = act.get('cells')
                if cells is not None:
                    zxsa = [i.get('value') for i in cells if i.get('id') == 26]
                    if zxsa:
                        all_times.extend(zxsa)
            amount = sum(all_times)
            self.total_duration += amount

            previous_day = rday

        # # # очищаем продолжительность в update_table_row_all
        self.total_duration2 = self.total_duration
        if len(set(list_reset)) > 0:
            for row in self.update_table_row_all:
                if row['row_id'] in list_reset:
                    if row.get('cells', None) is None:
                        continue

                    for cell in row['cells']:
                        if cell['id'] == 26 and cell['value'] is not None:
                            # self.total_duration2 -= cell['value']
                            cell['value'] = 0
        if all_list_delete:
            self.update_table_row_all = [item for i, item in enumerate(self.update_table_row_all)
                                         if i not in frozenset(all_list_delete)]

        # Переработки / недоработки с предыдущего месяца
        if self.task_body.get('previous_over_time') is not None:
            overtime_cell_updates = []
            empl_id = self.task_body.get('employee_id')
            if self.task_body.get('previous_over_time').get(empl_id) is not None:
                reason_dayoff = (self.task_body.get('previous_over_time').get(empl_id))[2]
                previous_overtime_task_id = self.task_body.get('previous_over_time').get(self.task_body.get('employee_id'))[0]
                amount = self.task_body.get('previous_over_time').get(self.task_body.get('employee_id'))[1]
                overtime_cell_updates.append({'id': 89, 'value': amount})
                overtime_cell_updates.append({'id': 92, 'value': f"{reason_dayoff} https://pyrus.com/t#id{previous_overtime_task_id}"})

                update_table_row = {'row_id': self.overtime_new_row, 'cells': overtime_cell_updates,
                                    'day_st': '1900-01-01' + '00:00'}

                self.overtime_new_row += 1
                self.update_overtime_table_row_all.append(update_table_row)
                self.overtime += amount
                self.pre_overtime = amount

        newlist = sorted(self.update_table_row_all, key=lambda d: [d['day_st']], reverse=False)
        self.update_table_row_all = [{'row_id': newlist.index(i), 'cells': i['cells']} for i in newlist]

        self.field_updates.append({'id': 9, 'value': self.update_table_row_all})
        self.field_updates.append({'id': 29, 'value': self.amount_working_day})

        if self.update_hot_line_table_row_all:
            newlist = sorted(self.update_hot_line_table_row_all, key=lambda d: [d['day_st']], reverse=False)
            self.update_hot_line_table_row_all = [{'row_id': newlist.index(i), 'cells': i['cells']} for i in newlist]
            self.field_updates.append({'id': 40, 'value': self.update_hot_line_table_row_all})
            self.field_updates.append({'id': 45, 'value': self.night_duty})
            self.field_updates.append({'id': 46, 'value': self.day_duty})

        if self.update_overtime_table_row_all:
            newlist = sorted(self.update_overtime_table_row_all, key=lambda d: [d['day_st']], reverse=False)
            self.update_overtime_table_row_all = [{'row_id': newlist.index(i), 'cells': i['cells']} for i in newlist]
            self.field_updates.append({'id': 87, 'value': self.update_overtime_table_row_all})

        if self.update_dezhurstvo_table_row_all:
            newlist = sorted(self.update_dezhurstvo_table_row_all, key=lambda d: [d['day_st']], reverse=False)
            self.update_dezhurstvo_table_row_all = [{'row_id': newlist.index(i), 'cells': i['cells']} for i in newlist]
            self.field_updates.append({'id': 66, 'value': self.update_dezhurstvo_table_row_all})

            self.field_updates.append({'id': 72, 'value': self.day_st_duty_week})
            self.field_updates.append({'id': 73, 'value': self.night_st_duty_week})
            self.field_updates.append({'id': 74, 'value': self.day_st_duty_weekend})
            self.field_updates.append({'id': 75, 'value': self.night_st_duty_weekend})
            self.field_updates.append({'id': 76, 'value': self.day_st_duty_holiday})
            self.field_updates.append({'id': 77, 'value': self.night_st_duty_holiday})

        if self.update_error_entrance_table_row_all:
            self.field_updates.append({'id': 100, 'value': self.update_error_entrance_table_row_all})

        if self.overtime != 0:
            # новая логика
            # Если был перенос времени из предыдущего периода, то из него вычитаем все недоработки.
            # Если будет положительное число(переработки все еще есть), то их уже не учитываем в этом поле Итого, а учитываем только переработки текущего месяца.
            # Если будет отрицательное, то добавляем в этим отрицательным текущие переработки и заносим в Итого
            itogo_perenos = 0
            if self.pre_overtime >= 0:
                itogo_perenos = self.pre_overtime + self.overtime_minus # из переработки предыдущей вычитаем все недоработки текущего месяца.
                if itogo_perenos > 0: # Переработки в прошлом месяце минус недоработки в этом, если больше 0, то на следующий месяц не переносим
                    itogo_perenos = 0 + self.overtime_plus # Добавляем переработки в этом месяце
                else:
                    itogo_perenos = itogo_perenos + self.overtime_plus

            else:
                itogo_perenos = self.pre_overtime + self.overtime_plus  # из недоработки предыдущей вычитаем все переработки текущего месяца.
                itogo_perenos = itogo_perenos + self.overtime_minus     # и так же вычитаем недоработки текущего месяца.

            hours = int(itogo_perenos)
            minutes = (itogo_perenos - hours) * 60
            if itogo_perenos > 0:
                self.field_updates.append({'id': 91, 'value': {'choice_id': 1}})
            else:
                self.field_updates.append({'id': 91, 'value': {'choice_id': 2}})
            self.field_updates.append({'id': 83, 'value': abs(hours)})
            self.field_updates.append({'id': 84, 'value': abs(minutes)})
        else:
            self.field_updates.append({'id': 91, 'value': {'choice_id': None}})
            self.field_updates.append({'id': 83, 'value': 0})
            self.field_updates.append({'id': 84, 'value': 0})

        if self.range_vr:
            range_vr = range_days_off(self.range_vr)
            self.field_updates.append({'id': 35, 'value': range_vr})

        if self.range_vyo:
            range_vyo = range_days_off(self.range_vyo)
            self.field_updates.append({'id': 36, 'value': range_vyo})

        if self.range_sd:
            range_sd = range_days_off(self.range_sd)
            self.field_updates.append({'id': 37, 'value': range_sd})

        if self.range_do:
            range_do = range_days_off(self.range_do)
            self.field_updates.append({'id': 38, 'value': range_do})

        self.field_updates.append({'id': 54, 'value': self.visits})
        self.field_updates.append({'id': 57, 'value': f'Звонки: {self.calling}/ Переписки: {self.texting}'})

        try:
            self.average_duration = self.total_duration2 / self.amount_working_day
        except:
            self.average_duration = 0

        self.field_updates.append({'id': 30, 'value': self.average_duration})
        self.field_updates.append({'id': 79, 'value': round(self.total_duration2, 2)})
        self.field_updates.append({'id': 80, 'value': self.ip_post})

        self.field_updates.append({'id': 86, 'value': self.work_day_must_be})

        self.field_updates.append({'id': 114, 'value': self.dop_pay})

        self.msql.db.close()
        return 200
