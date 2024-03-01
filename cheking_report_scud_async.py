'''
creating
Запускаем 1 раз в месяц.
Создает задачи на каждого сотрудника в форме Отчет сотрудника (СКУД) https://pyrus.com/t#fc1261472

checking
Заполняем:
- общую информацию (Отчет за, Персональные данные сотрудника, Сотрудник, Должность фактическая, Подразделение фактическое,
Рабочее место, График работы, Время работы с, Время работы по, Руководитель отдела)
- Кол-во календарных дней в месяце
- Кол-во часов при 40-часовой р.н.
- Кол-во часов при 36-часовой р.н.
- Статус

Скрипт отрабатывает каждый день один раз форме Отчет сотрудника (СКУД) https://pyrus.com/t#fc1261472
Выбирает по реестру задачи со статусом "Заполнение".
Запускает заполнение таблицы для бэк офиса единожды за месяц, для выездной каждый день по одной строке

Создание - 07.07.2023 Андрей.
Последнее обновление - ..2023 Андрей.
'''
import asyncio
import multiprocessing
import sys
# from multiprocessing import Pool
import datetime
import logging
import time

from mayak_help_lib import DataInterface, Task
from mayak_help_lib.scud import fill_scud_report


data = DataInterface()


def start_process(each_task, period_report, dict_exist_overtimes, clear_tbl=False):

    department_id = 4
    employee_id = 2
    report_tbl_id = 9
    dezhur_tbl_id = 66
    overtime_tbl_id = 87
    error_entrance_tbl_id = 100

    each_task = Task(task_id=each_task)

    task_body = {}
    print(period_report)
    step = None
    month_report = int(each_task.plain_body.get(27)['values'][1])
    year_report = int(each_task.plain_body.get(27)['values'][2])
    if period_report.get('period_report') is not None:
        task_body.update({'month_report': month_report, 'year_report': year_report})
    else:
        first_day_report = period_report.get('first_day_report')
        last_day_report = period_report.get('last_day_report')
        task_body.update({'first_day_report': first_day_report, 'last_day_report': last_day_report})

        # Если последний день месяца, то "Этап маршрутизации" id112 = "Конец месяца", если другой день, то "Полмесяца"
        month_report = month_report if len(str(month_report)) > 1 else f'0{month_report}'
        x = f"{year_report}-{month_report}-{each_task.plain_body.get(27)['values'][6]}"
        if f"{x}" == last_day_report:
            step = 3
        else:
            step = 2

    amount_calendar_days = int(each_task.plain_body.get(27)['values'][6])
    try:
        grafik = float(each_task.plain_body.get(15)['values'][1])
    except:
        grafik = None

    # Ставка
    stavka = each_task.plain_body.get(81)
    amount_working_days = each_task.plain_body.get(31)

    lead_Lida = False
    if each_task.plain_body.get(6):
        if each_task.plain_body.get(6)['id'] == 411396:
            lead_Lida = True

    task_body.update({'amount_calendar_days': amount_calendar_days, 'grafik': grafik, 'stavka': stavka,
                      'amount_working_days': amount_working_days, 'lead_Lida': lead_Lida})

    if each_task.plain_body.get(employee_id) is not None:
        employee = each_task.plain_body.get(employee_id)['item_id']
        task_body.update({'employee_id': employee})

    if each_task.plain_body.get(department_id) is not None:
        department = each_task.plain_body.get(department_id)['item_id']
        task_body.update({'department': department})

    if dict_exist_overtimes:
        task_body.update({'previous_over_time': dict_exist_overtimes})

    place_work = None
    if each_task.plain_body.get(14) is not None:
        place_work = each_task.plain_body.get(14)
    task_body.update({'place_work': place_work})

    exist_main_table_row_all = []
    update_true = 'Обновить'

    async def clear_form_tables(each_task):
        clear_flag = False
        tbl_list = []

        # **************
        # Формируем основную таблицу для последующего сравнения и очищаем её
        table_rows = each_task.plain_body.get(report_tbl_id)
        if table_rows is not None:
            for row in table_rows:
                if row.get('cells', None) is None:
                    continue
                cells_updates = []
                plain_row = {cell['id']: cell['value'] for cell in row['cells']}
                if plain_row.get(34):
                    cells_updates.append({'id': 34, 'value': plain_row.get(34)})
                if plain_row.get(10):
                    cells_updates.append({'id': 10, 'value': plain_row.get(10)})
                if plain_row.get(20):
                    cells_updates.append({'id': 20, 'value': plain_row.get(20)})
                # Вид занятости
                if plain_row.get(13):
                    cells_updates.append({'id': 13, 'value': {'item_id': plain_row.get(13)['item_id']}})
                # Время нач. / Время оконч.
                if plain_row.get(11):
                    cells_updates.append({'id': 11, 'value': plain_row.get(11)})
                if plain_row.get(12):
                    cells_updates.append({'id': 12, 'value': plain_row.get(12)})
                # Время в дороге
                if plain_row.get(28):
                    cells_updates.append({'id': 28, 'value': plain_row.get(28)})
                # Итого часов
                if plain_row.get(26):
                    cells_updates.append({'id': 26, 'value': plain_row.get(26)})
                # Ссылка на задачу
                if plain_row.get(12):
                    cells_updates.append({'id': 19, 'value': plain_row.get(19)})
                # Комментарий
                if plain_row.get(25):
                    cells_updates.append({'id': 25, 'value': plain_row.get(25)})
                # Пациент
                if plain_row.get(21):
                    cells_updates.append({'id': 21, 'value': {'item_ids': plain_row.get(21)['item_ids']}})

                # заполняем строку
                update_table_row = {'row_id': row.get('row_id'), 'cells': cells_updates}
                exist_main_table_row_all.append(update_table_row)

            clear_flag = True
            tbl_list.append(report_tbl_id)
        # **************

        # Очисти таблицу дежурства в стационаре
        table_rows = each_task.plain_body.get(dezhur_tbl_id)
        if table_rows is not None:
            clear_flag = True
            tbl_list.append(dezhur_tbl_id)

        # Очисти таблицу Переработки и недоработки
        table_rows = each_task.plain_body.get(overtime_tbl_id)
        if table_rows is not None:
            clear_flag = True
            tbl_list.append(overtime_tbl_id)

        # # Очисти таблицу Если СКУД не зафиксировал вход или выход
        # table_rows = each_task.plain_body.get(error_entrance_tbl_id)
        # if table_rows is not None:
        #     clear_flag = True
        #     tbl_list.append(error_entrance_tbl_id)

        if clear_flag:
            fld_upd = []
            # Очистка таблиц
            # так как кнопкой тоже можем очищать, то придётся завязываться на поле, а не на статус бота
            if clear_tbl:
                fld_upd = [{'id': 113, 'value': 'checked'}]

            data.session.clear_X_rows_in_N_tables(task_id=each_task.task_id, tbl_list=tbl_list, x_rows=200, dlt=True,
                                                  fld_upd=fld_upd)

    async def exist_table_data(each_task):
        await asyncio.gather(clear_form_tables(each_task))

    # async def exist_table_data(each_task):
    #     await asyncio.gather(main_table(each_task), duty_table(each_task), overtime_table(each_task), error_entrance_table(each_task))

    asyncio.run(exist_table_data(each_task))

    print(f'Собираем данные из разных БД по сотруднику из задачи {each_task.task_id} {each_task.plain_body.get(employee_id)["values"][1]} - {each_task.plain_body.get(employee_id)["item_id"]}')

    start = time.time()
    print(f'Запуск fill_scud report {start}')
    prepare_data = fill_scud_report.ScudReport(data=data, task_body=task_body)
    field_updates = prepare_data.field_updates
    print(f'Время выполнения {time.time() - start}')  ## вывод времени

    print('Обработка данных.')
    upd_row_all = []
    new_row = 1
    for i in prepare_data.update_table_row_all:
        new_cells = i['cells']
        new_comparable_id = [k.get('value') for k in new_cells if k['id'] == 34][0]
        cells_updates = new_cells
        for index, cells in enumerate(exist_main_table_row_all):
            exist_cell = cells['cells']
            exist_comparable_id = [k.get('value') for k in exist_cell if k['id'] == 34][0]
            if str(new_comparable_id) == str(exist_comparable_id) and update_true is None:
                cells_updates = exist_cell
                exist_main_table_row_all.pop(index)
                break

        # заполняем строку
        update_table_row = {'row_id': new_row, 'cells': cells_updates}
        new_row += 1
        upd_row_all.append(update_table_row)

    fld_index = [i for i, k in enumerate(prepare_data.field_updates) if k.get('id') == 9][0]
    field_updates[fld_index] = {'id': 9, 'value': upd_row_all}

    if step is not None:
        field_updates.append({'id': 112, 'value': {'choice_id': step}})

    text = 'Данные заполнены'
    update_json = {'field_updates': field_updates, 'text': text}
    reply = data.session.update_task_reply(
        task_id=each_task.task_id,
        update_json=update_json
    )
    if reply.ok:
        print(text)
        return 200
    else:
        logging.error(f'Данные не получилось заполнить #{each_task.task_id}')
        print(f'{reply.text}')
        return 400


def main(task_body):
    '''
    start_date = '2023-08-01'                       # отчетный месяц
    person_item_id = 80431721                       # сотрудник по которому формируем отчет
    group_department = 182579871       # Группа-подразделение для табеля
    task_body = {
                 '24': {'item_id': person_item_id},
                 '7': start_date,
                 '41': group_department
    }
    '''

    period_report = {}
    update_true = task_body.get('status')
    status_task = True
    action_task = 'finished'

    start = time.time()
    error_text = ''

    clear_tbl = task_body.get('clear_tbl', False)

    # отчетный месяц
    first_day_report = task_body.get('7')
    last_day_report = task_body.get('8')

    month_report = datetime.date(int(first_day_report[:4]), int(first_day_report[5:7]), int(first_day_report[8:])).month
    year_report = datetime.date(int(first_day_report[:4]), int(first_day_report[5:7]), int(first_day_report[8:])).year

    if last_day_report is not None:
        period_report['first_day_report'] = first_day_report
        period_report['last_day_report'] = last_day_report
    else:
        period_report['period_report'] = first_day_report

    # Справочник Производственный календарь
    catalog = data.session.get_catalog_reply(186824).json().get('items')
    item_id_calendar = [i['item_id'] for i in catalog if i.get('values')[1] == str(month_report) and
                        i.get('values')[2] == str(year_report)][0]

    if month_report > 1:
        item_id_previous_report = [i['item_id'] for i in catalog if i.get('values')[1] == str(month_report - 1) and
                                   i.get('values')[2] == str(year_report)][0]
    else:
        item_id_previous_report = [i['item_id'] for i in catalog if i.get('values')[1] == str(12) and
                            i.get('values')[2] == str(year_report-1)][0]

    amount_month_days = int([i['values'][3] for i in catalog if i.get('values')[1] == str(month_report) and
                             i.get('values')[2] == str(year_report)][0])
    amount_month_hours_40 = float([i['values'][4] for i in catalog if i.get('values')[1] == str(month_report) and
                                   i.get('values')[2] == str(year_report)][0])
    amount_month_days_36 = float([i['values'][5] for i in catalog if i.get('values')[1] == str(month_report) and
                                  i.get('values')[2] == str(year_report)][0])
    amount_month_days_35 = float([i['values'][7] for i in catalog if i.get('values')[1] == str(month_report) and
                                  i.get('values')[2] == str(year_report)][0])

    person_item_id = None
    if task_body.get('24') is not None:
        person_item_id = task_body.get('24')['item_id']

    group_department = None
    if task_body.get('41') is not None:
        group_department = task_body.get('41')

    stop_person_list_of_roles = []

    searching_dict_scud, searching_dict_pd = {}, {}

    # Условия поиска по пд и в отчетах скуд
    data_search_pd_dep, data_search_pd_empl, data_search_pd_okrug = '', '', ''
    data_search_scud_dep, data_search_scud_empl, data_search_scud_okrug = '', '', ''
    print(task_body)
    # 1 - Создание отчетов за период по всем сотрудникам
    print('1 - Создание отчетов за период по всем сотрудникам')
    if person_item_id is None:
        all_department_ids = []     # Список департаментов для формирования отчета
        all_employee_ids = []       # Список сотрудников для формирования отчета
        okrug_ids = []              # Список округов для формирования отчета

        # Группа-подразделение для табеля. Формируем отчеты по сотрудникам (СКУД) и табель стоит галочка
        if group_department is None:
            group_department = data.session.get_register_filtered_reply(
                form_id=1311411,
                archived='n',
                search=f'fld4=checked'
            ).json().get('tasks', [])
            for each_dep in group_department:
                task = Task(task_id=each_dep['id'])
                if task.plain_body.get(2) is not None:      # Какие подразделения входят в группу
                    department_ids = task.plain_body.get(2)['item_ids']
                    all_department_ids.extend(department_ids)
                elif task.plain_body.get(12) is not None:   # Какие сотрудники входят в группу
                    all_employee_ids.extend(task.plain_body.get(12)['item_ids'])
        else:
            department_task = Task(task_id=group_department)
            if department_task.plain_body.get(2) is not None:
                all_department_ids.extend(department_task.plain_body.get(2)['item_ids'])
            elif department_task.plain_body.get(12) is not None:
                all_employee_ids.extend(department_task.plain_body.get(12)['item_ids'])
            # Проверка если это конкретный округ - добавляем id округа и формируем поиск по округу иначе по департаменту
            if department_task.plain_body.get(10) == 'checked':
                okrug_ids.append(department_task.plain_body.get(11)['item_id'])

        if all_department_ids:
            dep = ','.join([str(i) for i in set(all_department_ids)])
            data_search_pd_dep += f'fld43={dep}'
            data_search_scud_dep += f'fld4={dep}'
            searching_dict_scud.update({'search_by_dep': data_search_scud_dep})
            searching_dict_pd.update({'search_by_dep': data_search_pd_dep})

        if all_employee_ids:
            empl = ','.join([str(i) for i in set(all_employee_ids)])
            data_search_pd_empl += f'fld14={empl}'
            data_search_scud_empl += f'fld2={empl}'
            searching_dict_scud.update({'search_by_empl': data_search_scud_empl})
            searching_dict_pd.update({'search_by_empl': data_search_pd_empl})

        if okrug_ids:
            okrug = ','.join([str(i) for i in set(okrug_ids)])
            data_search_pd_okrug += f'fld49={okrug}'
            data_search_scud_okrug += f'fld56={okrug}'
            searching_dict_scud.update({'search_by_okrug': data_search_scud_okrug})
            searching_dict_pd.update({'search_by_okrug': data_search_pd_okrug})
    else:
        data_search_pd_empl += f'fld14={person_item_id}'
        data_search_scud_empl += f'fld2={person_item_id}'
        searching_dict_scud.update({'search_by_empl': data_search_scud_empl})
        searching_dict_pd.update({'search_by_empl': data_search_pd_empl})

    # Формируем перечень существующих отчетов
    print('Формируем перечень существующих отчетов')
    for i in searching_dict_scud:
        data_search = f'fld27={item_id_calendar}&{searching_dict_scud.get(i)}'
        filter_exist_report = data.session.get_register_filtered_reply(
            form_id=1261472,
            archived='n',
            search=data_search
        ).json().get('tasks', [])

        if filter_exist_report:
            filter_exist_report = [et.get('fields')[1]['value']['item_id'] for et in filter_exist_report]
            stop_person_list_of_roles.extend(filter_exist_report)

    # Формируем наличие переработок в прошлом отчете
    print('Формируем наличие переработок в прошлом отчете')
    dict_exist_overtimes = {}
    for i in searching_dict_scud:
        data_search = f'fld27={item_id_previous_report}&{searching_dict_scud.get(i)}&field_ids=2,48,91,83,84,93,104,106,107'
        filter_previous_report = data.session.get_register_filtered_reply(
            form_id=1261472,
            archived='y',
            search=data_search
        ).json().get('tasks', [])

        for previous_report_task in filter_previous_report:
            # print(previous_report_task['id'])
            # if previous_report_task['id'] == 201187822:
            #     print(0)
            if len(previous_report_task['fields']) > 1:
                e_id = previous_report_task['fields'][0]['value']['item_id']
                if previous_report_task['fields'][2].get('value') is not None:
                    solution = previous_report_task['fields'][2].get('value').get('choice_ids')
                elif previous_report_task['fields'][3].get('value') is not None:
                    solution = previous_report_task['fields'][3].get('value').get('choice_ids')
                else:
                    solution = None
                if solution is not None:
                    fields = previous_report_task['fields'][1].get('value').get('fields')
                    debt = [i['value'] for i in fields if i['id'] == 91]
                    if debt and debt[0].get('choice_id') == 1 and (1 in solution and 2 in solution):
                        fields = previous_report_task['fields']
                        debt_time = fields[4].get('value', 0) + (fields[5].get('value', 0) / 60)
                        solution_text = 'перенос переработки из прошлого месяца'
                        dict_exist_overtimes[e_id] = [previous_report_task['id'], debt_time, solution_text]
                    elif debt and debt[0].get('choice_id') == 1 and 1 in solution:
                        fields = previous_report_task['fields'][1]['value']['fields']
                        debt_time = fields[0].get('value', 0) + (fields[1].get('value', 0) / 60)
                        solution_text = 'перенос переработки из прошлого месяца'
                        dict_exist_overtimes[e_id] = [previous_report_task['id'], debt_time, solution_text]
                    elif debt and debt[0].get('choice_id') == 2 and 1 in solution:
                        solution_text = 'недоработка перенесена из прошлого месяца'
                        debt_time = (fields[0].get('value', 0) + (fields[1].get('value', 0) / 60)) * -1
                        dict_exist_overtimes[e_id] = [previous_report_task['id'], debt_time, solution_text]

    progressVis = {0: ' ', 1: '- ', 2: '-- ', 3: '--- ', 4: '---- ', 5: '----- ',
                   6: '------ ', 7: '------- ', 8: '-------- ', 9: '--------- ', 10: '----------'}
    # Формируем реестр ПД по нужным для отчета параметрам
    print('Формируем реестр ПД по нужным для отчета параметрам')
    waint_minute = False
    filter_data_tasks = []
    for i in searching_dict_pd:
        filter_data_tasks1 = data.session.get_register_filtered_reply(
            form_id=802538,
            archived='n',
            search=f'{searching_dict_pd.get(i)}'
        ).json().get('tasks', [])
        if filter_data_tasks1:
            filter_data_tasks1 = [t['id'] for t in filter_data_tasks1]
            filter_data_tasks.extend(filter_data_tasks1)
    if filter_data_tasks:
        amount_f = len(set(filter_data_tasks))
        for row_num, each_task in enumerate(set(filter_data_tasks)):
            each_task = Task(task_id=each_task)
            percent = int((float(row_num + 1) / amount_f) * 10)
            str1 = "\r \r [{0}] {1}/{2} {3}% - {4}".format(progressVis[percent], row_num + 1, amount_f,
                                                           round(((row_num + 1) * 100 / amount_f), 2), each_task.task_id)
            sys.stdout.write(str1)
            sys.stdout.flush()

            field_updates = []

            # item_id сотрудника
            if each_task.plain_body.get(14) is None:
                continue
            if each_task.plain_body.get(14)['item_id'] in stop_person_list_of_roles:
                continue

            # проверка Дата начала работы в ДХ
            date_dh = each_task.plain_body.get(8)
            if date_dh is None:
                continue

            #  сотрудник принят на работу не в этот отчетный месяц, а позже, тогда не формируем
            if date_dh > first_day_report:
                month_date_dh = datetime.date(int(date_dh[:4]), int(date_dh[5:7]), int(date_dh[8:])).month
                if month_date_dh > month_report:
                    continue

            # Задача
            task_id = each_task.task_id
            # print(each_task.task_id)
            field_updates.append({'id': 1, 'value': {'task_id': task_id}})

            # Статус сотрудника
            if each_task.plain_body.get(14)['values'][5] != 'работает':
                continue

            employee_id = each_task.plain_body.get(14)['item_id']
            field_updates.append({'id': 2, 'value': {'item_id': employee_id}})

            # Подразделение фактическое
            if each_task.plain_body.get(43) is None:
                continue

            dep_employee = each_task.plain_body.get(43)['item_id']
            field_updates.append({'id': 4, 'value': {'item_id': dep_employee}})

            # Округ Москвы
            if each_task.plain_body.get(49) is not None:
                field_updates.append({'id': 56, 'value': {'item_id': each_task.plain_body.get(49)['item_id']}})

            # должность
            if each_task.plain_body.get(17) is not None:
                field_updates.append({'id': 3, 'value': {'item_id': each_task.plain_body.get(17)['item_id']}})

            # Рабочее место
            if each_task.plain_body.get(60) is not None:
                field_updates.append({'id': 14, 'value': {'item_id': each_task.plain_body.get(60)['item_id']}})

            # График работы
            if each_task.plain_body.get(63) is not None:
                field_updates.append({'id': 15, 'value': {'item_id': each_task.plain_body.get(63)['item_id']}})

            # Время работы с
            if each_task.plain_body.get(61) is not None:
                field_updates.append({'id': 16, 'value': each_task.plain_body.get(61)})

            # Время работы по
            if each_task.plain_body.get(62) is not None:
                field_updates.append({'id': 17, 'value': each_task.plain_body.get(62)})

            # Руководитель отдела
            if each_task.plain_body.get(18) is not None:
                field_updates.append({'id': 6, 'value': {'id': each_task.plain_body.get(18)['id']}})

            # Статус задачи на "заполнение"
            field_updates.append({'id': 24, 'value': {'choice_id': 1}})

            # Отчет за период
            field_updates.append({'id': 27, 'value': {'item_id': item_id_calendar}})

            # Время на обед
            if each_task.plain_body.get(78) is not None:
                field_updates.append({'id': 60, 'value': each_task.plain_body.get(78)})

            # Ставка
            stavka = each_task.plain_body.get(84)
            if stavka is not None:
                stavka = stavka.replace(',', '.')
                try:
                    stavka = float(stavka)
                except:
                    stavka = 1
            else:
                stavka = 0

            field_updates.append({'id': 81, 'value': stavka})

            # Этап маршрутизации
            # Выбор: Тест(1), Полмесяца(2), Конец месяца(3)
            field_updates.append({'id': 112, 'value': {'choice_id': 2}})

            # Кол-во рабочих дней в месяце
            field_updates.append({'id': 31, 'value': amount_month_days})

            # Кол-во часов при 40-часовой р.н.
            field_updates.append({'id': 32, 'value': amount_month_hours_40 * stavka})

            # Кол-во часов при 36-часовой р.н.
            field_updates.append({'id': 33, 'value': amount_month_days_36 * stavka})

            # Кол-во часов при 35-часовой р.н.
            field_updates.append({'id': 96, 'value': amount_month_days_35 * stavka})

            # Создаем задачу
            new_json = {'form_id': 1261472, 'fields': field_updates}
            reply = data.session.create_task_reply(
                new_json=new_json
            )
            if not reply.ok:
                logging.error(reply.text)
            else:
                waint_minute = True
                print('создал')

    if update_true is None and waint_minute:
        print('ждем 1 минуту')
        time.sleep(60)

    filling_task_ids = []
    # 2 - Заполнение отчетов по всем сотрудникам
    for i in searching_dict_scud:
        print('формируем лист id задач отчетов')
        filter_data_tasks = data.session.get_register_filtered_reply(
            form_id=1261472,
            archived='n',
            search=f'fld27={item_id_calendar}&{searching_dict_scud.get(i)}'        # Сформирован выше стр 65 - 112
        ).json().get('tasks', [])

        if filter_data_tasks:
            filter_data_tasks = [t['id'] for t in filter_data_tasks]
            filling_task_ids.extend(filter_data_tasks)

    print(f'начали {len(filling_task_ids)}')
    if task_body.get('status') == 'В любом случае обновляем.':
        print('В любом случае обновляем.')
        start_process(task_body.get('task_id'), period_report, dict_exist_overtimes, clear_tbl)
    else:
        print('multiprocessing')
        size_list = len(filling_task_ids)
        if size_list == 1:
            start_process(filling_task_ids[0], period_report, dict_exist_overtimes, clear_tbl)
        elif 1 < size_list <= 4:
            procs = []
            for i in filling_task_ids:
                p = multiprocessing.Process(target=start_process, args=(i, period_report, dict_exist_overtimes, clear_tbl))
                procs.append(p)
                p.start()
            print('Ждем результаты...')
            # блокируем дальнейшее выполнение программы
            # пока не закончат выполняться все 5 потоков
            [proc.join() for proc in procs]
            print('Результаты получены.')
        else:
            print('Взял в обработку > 4')
            split_list = [filling_task_ids[i: i + 4] for i in range(0, len(filling_task_ids), 4)]
            print(len(split_list))
            for eac_list in split_list:
                procs = []
                # запускаем функцию 'start_process()'
                # для выполнения в 4 потоках
                for i in eac_list:
                    p = multiprocessing.Process(target=start_process, args=(i, period_report, dict_exist_overtimes, clear_tbl))
                    procs.append(p)
                    p.start()
                print('Ждем результаты...')
                # блокируем дальнейшее выполнение программы
                # пока не закончат выполняться все 4 потоков
                [proc.join() for proc in procs]
                print('Результаты получены.')

    end = time.time() - start
    print(f'Время выполнения: {end}')
    now = datetime.datetime.now()
    date_finish = now.strftime("%d-%m-%Y %H:%M")
    text_response = f'Создано / обновлено. \n{error_text}'

    if update_true is not None:
        if error_text == '':
            text_response = f'Время выполнения: {end}'
            reply_code = 200
            return reply_code, text_response
        else:
            text_response = f'Есть ошибки обновления! Время выполнения: {end}'
            reply_code = 400
            return reply_code, text_response
    else:
        return status_task, text_response, date_finish, action_task


if __name__ == '__main__':
    # по сотруднику
    # start_date = '2023-12-01'         # отчетный месяц
    # person_item_id = None           # 82373762, 80431721   сотрудник по которому формируем отчет
    group_department = None           # IT - 182579871   ЮГо-ВОсток - 182579506

    data_task = Task(task_id=203205471)

    person_item_id = data_task.plain_body.get(2)['item_id']           # 82373762, 80431721   сотрудник по которому формируем отчет
    # group_department = data_task.plain_body.get(4)['item_id']       # IT - 182579871   ЮГо-ВОсток - 182579506
    status = 'В любом случае обновляем.'

    # task_body = {
    #              '24': {'item_id': person_item_id},
    #              '7': start_date,
    #              '41': group_department,
    #              'status': status,
    #              'task_id': data_task.task_id
    # }

    first_day_report = '2024-02-20'
    last_day_report = '2024-02-29'
    task_body = {
                 '24': {'item_id': person_item_id},
                 '7': first_day_report,
                 '8': last_day_report,
                 '41': group_department,
                 'status': status,
                 'task_id': data_task.task_id
    }

    text_response = main(task_body=task_body)
    print(text_response)
