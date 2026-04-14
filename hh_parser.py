import requests
import time
import json
import csv
from datetime import datetime
from tqdm import tqdm
import os


class HHParser:
    
    BASE_URL = "https://api.hh.ru"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json'
        })
        
    def search_vacancies(self, text: str, area: int = 1, per_page: int = 100, pages: int = 1):
        """
        Поиск вакансий по ключевому слову
        
        :param text: поисковый запрос (например, "Python разработчик")
        :param area: регион (1 - Москва, 2 - Санкт-Петербург, 113 - Россия)
        :param per_page: количество на странице (макс 100)
        :param pages: количество страниц для загрузки
        :return: список сырых данных с API
        """
        url = f"{self.BASE_URL}/vacancies"
        all_items = []
        
        params = {
            'text': text,
            'area': area,
            'per_page': min(per_page, 100),  
            'page': 0
        }
        
        print(f"Поиск вакансий по запросу: {text}")
        
        for page in tqdm(range(pages), desc="Загрузка страниц"):
            params['page'] = page
            
            try:
                response = self.session.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                
                items = data.get('items', [])
                all_items.extend(items)

                if page >= data.get('pages', 0) - 1:
                    break

                time.sleep(1)
                
            except requests.exceptions.RequestException as e:
                print(f"Ошибка при загрузке страницы {page}: {e}")
                break
                
        print(f"Найдено вакансий: {len(all_items)}")
        return all_items
    
    def get_vacancy_details(self, vacancy_id: str):

        """Получение подробной информации по конкретной вакансии"""

        url = f"{self.BASE_URL}/vacancies/{vacancy_id}"
        
        try:
            response = self.session.get(url)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Ошибка при загрузке вакансии {vacancy_id}: {e}")
            return None
    
    def parse_vacancies(self, search_query: str, max_pages: int = 5, with_details: bool = True):
        """
        Полный парсинг вакансий: поиск + детали
        
        :param search_query: поисковый запрос
        :param max_pages: максимум страниц для загрузки
        :param with_details: загружать ли детальную информацию
        :return: список обработанных вакансий
        """
        vacancies = self.search_vacancies(
            text=search_query,
            pages=max_pages,
            per_page=100
        )
        
        result = []
        
        if with_details:
            print("Загрузка детальной информации...")
            for vac in tqdm(vacancies, desc="Обработка вакансий"):
                details = self.get_vacancy_details(vac['id'])
                if details:
                    processed = self._process_vacancy(details)
                    result.append(processed)
                time.sleep(0.3) 
        else:
            for vac in vacancies:
                processed = self._process_vacancy(vac)
                result.append(processed)
                
        return result
    
    def _process_vacancy(self, data: dict) -> dict:

        salary = data.get('salary')
        salary_from = None
        salary_to = None
        salary_currency = None
        
        if salary:
            salary_from = salary.get('from')
            salary_to = salary.get('to')
            salary_currency = salary.get('currency')
        
        salary_str = 'не указана'
        if salary_from and salary_to:
            salary_str = f"{salary_from} - {salary_to} {salary_currency}"
        elif salary_from:
            salary_str = f"от {salary_from} {salary_currency}"
        elif salary_to:
            salary_str = f"до {salary_to} {salary_currency}"
        
        key_skills = [skill['name'] for skill in data.get('key_skills', [])]
        
        description = data.get('description', '')
        import re
        description_clean = re.sub(r'<[^>]+>', '', description) if description else ''
        
        return {
            'id': data.get('id'),
            'name': data.get('name'),
            'employer': data.get('employer', {}).get('name') if data.get('employer') else None,
            'area': data.get('area', {}).get('name') if data.get('area') else None,
            'salary_from': salary_from,
            'salary_to': salary_to,
            'salary_currency': salary_currency,
            'salary_str': salary_str,
            'experience': data.get('experience', {}).get('name') if data.get('experience') else None,
            'employment': data.get('employment', {}).get('name') if data.get('employment') else None,
            'schedule': data.get('schedule', {}).get('name') if data.get('schedule') else None,
            'key_skills': key_skills,
            'skills_count': len(key_skills),
            'description': description_clean[:500] + '...' if len(description_clean) > 500 else description_clean,
            'url': data.get('alternate_url'),
            'published_at': data.get('published_at'),
            'created_at': datetime.now().isoformat()
        }
    
    def save_to_json(self, data: list, filename: str = None): 
        if filename is None:
            filename = f"vacancies_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"Данные сохранены в {filename}")
        return filename
    
    
    def print_stats(self, data: list):
  
        print("\nСтатистика:")
        print(f"Всего вакансий: {len(data)}")
        
        employers = {}
        for vac in data:
            emp = vac.get('employer', 'Не указан')
            employers[emp] = employers.get(emp, 0) + 1
        
        print("\nТоп работодатели:")
        for emp, count in sorted(employers.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"  {emp}: {count} вакансий")
        
        all_skills = []
        for vac in data:
            all_skills.extend(vac.get('key_skills', []))
        
        from collections import Counter
        skill_stats = Counter(all_skills)
        
        print("\n🔧 Топ навыков:")
        for skill, count in skill_stats.most_common(10):
            print(f"  {skill}: {count} вакансий")
        salaries = [vac for vac in data if vac.get('salary_from') or vac.get('salary_to')]
        print(f"\nВакансий с указанной зарплатой: {len(salaries)}/{len(data)}")


def main():
    parser = HHParser()
    search_query = "Python разработчик" 
    max_pages = 3  
    
    print(f"Запуск парсера hh.ru")
    print(f"Запрос: {search_query}")
    print(f"Страниц: {max_pages}")
    print("-" * 30)
    
    vacancies = parser.parse_vacancies(
        search_query=search_query,
        max_pages=max_pages,
        with_details=True 
    )
    
    if vacancies:
        parser.save_to_json(vacancies)
    
        parser.print_stats(vacancies)

        print("\nПримеры вакансий:")
        for i, vac in enumerate(vacancies[:3], 1):
            print(f"\n{i}. {vac['name']}")
            print(f"   Компания: {vac['employer']}")
            print(f"   Зарплата: {vac['salary_str']}")
            print(f"   Опыт: {vac['experience']}")
            print(f"   Навыки: {', '.join(vac['key_skills'][:5])}")
            if len(vac['key_skills']) > 5:
                print(f"   ... и ещё {len(vac['key_skills']) - 5}")
    else:
        print("Не удалось загрузить вакансии")


if __name__ == "__main__":
    main()
