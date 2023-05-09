import asyncio
import nest_asyncio
import pandas as pd
import numpy as np
from playwright.async_api import Playwright, async_playwright
from numpy import genfromtxt
from collections import Counter

nest_asyncio.apply()

async def open(playwright: Playwright):
    browser = await playwright.chromium.launch(headless=False)
    context = await browser.new_context()
    page = await context.new_page()

    return page

async def run1(page, i: int, search_key: str, year_from: str, year_to: str):
    await page.goto("https://ieeexplore.ieee.org/search/searchresult.jsp?queryText="+search_key+"&highlight=false&returnType=SEARCH&matchPubs=true&sortType=newest&rowsPerPage=100&ranges="+year_from+"_"+year_to+"_Year&returnFacets=ALL&pageNumber="+str(i), timeout = 0)
    await page.wait_for_timeout(10000)
    
    all_elements = await page.query_selector_all('.result-item-align')
    data = []
    for element in all_elements:
        author_category = await element.query_selector('p.author.text-base-md-lh')
        if str(author_category) != None:
            result = dict()

            title_el = await element.query_selector('a.fw-bold')
            if title_el != None:
                result['title'] = await title_el.inner_text()
            else:
                try:
                    alt_title_el = await element.query_selector('text-md-md-lh')
                    alt_title_span = await alt_title_el.query_selector('span')
                    alt_title = await alt_title_span.inner_text()
                    result['title'] = alt_title
                    print("Title None: "+str(alt_title))
                except:
                    print("Title None")

            all_author = await element.query_selector_all('span.text-base-md-lh')
            author_el = []
            for person in all_author:
                person_q = await person.query_selector('a')
                if person_q != None:
                    author_el.append(await person_q.inner_text())
                    author_el.append(";")
            
            author_el = ''.join(author_el)
            result['authors'] = author_el

            j_el = await element.query_selector('.description')
            j = await j_el.query_selector('a')
            if j != None:
                result['publishedAt'] = await j.inner_text()
            else:
                print('Journal None At: '+ str(await title_el.inner_text()))
                result['publishedAt'] = "None"

            publisher_els = await element.query_selector('.publisher-info-container')
            publisher_el = await publisher_els.query_selector_all('span')

            year_el = publisher_el[0]
            result['year'] = await year_el.inner_text()
        
            pub_type_el = publisher_el[1]
            _pub_type = await pub_type_el.query_selector_all('span')
            pub_type = _pub_type[1]
            result['pub_type'] = await pub_type.inner_text()

            data.append(result)
        else:
            try:
                temp_title_el = await element.query_selector('a.fw-bold')
                temp_alt_title = str(await temp_title_el.inner_text())
                print("Element Not a Research Work"+temp_alt_title)
            except:
                print("Element Not a Research Work")

    # print(data)
    return data

async def run2(url: str):
    async with async_playwright() as playwright:
        page = await open(playwright)
        await page.goto(url+"keywords#keywords", timeout = 0)
        await page.wait_for_timeout(4000)

        keywords = []

        elements = await page.query_selector_all('li.doc-keywords-list-item')
        if (elements == None) or (len(elements) < 2):
            print("No keywords")
            return []
        else:
            author_key_el = elements[1]
            tar_key_el = await author_key_el.query_selector_all('a.stats-keywords-list-item')
            for key_el in tar_key_el:
                keywords.append(str(await key_el.inner_text()))

            return keywords

async def routine1(i: int, search_key: str, year_from: str, year_to: str):
    async with async_playwright() as playwright:
        page = await open(playwright)
        data_block = await run1(page, i, search_key, year_from, year_to)

        await asyncio.sleep(1)
        
        return data_block
   
async def routine2(urls: list):
        keywords = []

        loop = asyncio.get_event_loop()
        group = asyncio.gather(*[run2(url) for url in urls])
        results = loop.run_until_complete(group)

        for item in results:
            for i in item:
                keywords.append(i)

        await asyncio.sleep(1)

        return keywords
    
        
async def task_handler1(num: int, n_pages: int, search_key: str, year_from: str, year_to: str):
    full_data = []
    loop = asyncio.get_event_loop()

    num_start = num * 20 - 19
    num_fin = num_start + 20
    if num_fin > n_pages :
        num_fin = n_pages + 1
    group = asyncio.gather(*[routine1(i, search_key, year_from, year_to) for i in range(num_start, num_fin)])
    results = loop.run_until_complete(group)

    for item in results:
        for i in item:
            full_data.append(i)

    print('Tasks'+str(num)+' Done')

    df = pd.DataFrame.from_dict(full_data)
    df.to_csv('basic_infos.csv', index = False, mode='a', header=True)


async def task_handler2(i: int, search_key: str, year: str):
    async with async_playwright() as playwright:
        page = await open(playwright)
        search_target = "https://ieeexplore.ieee.org/search/searchresult.jsp?queryText="+search_key+"&highlight=false&returnType=SEARCH&matchPubs=true&sortType=newest&rowsPerPage=100&ranges="+year+"_"+year+"_Year&returnFacets=ALL&pageNumber="+str(i)
        await page.goto(search_target, timeout = 0)
        await page.wait_for_timeout(10000)

        all_elements = await page.query_selector_all('.result-item-align')
        urls = []
        for element in all_elements:
            hrefs = await element.eval_on_selector_all("a[href^='/document']", "elements => elements.map(element => element.href)")
            href = str(hrefs[0])
            urls.append(href)

        len_urls = len(urls)
        keywords = []
        
        for j in range(5):
            k = j * 10
            l = k + 20
            if l > len_urls + 1 :
                l = len_urls + 1
            sliced_urls = urls[k:l]
            part_keywords = await routine2(sliced_urls)
            for key in part_keywords:
                keywords.append(key)
        new_df = pd.DataFrame(keywords)
        new_df.to_csv('keywords.txt', index = False, mode='a', header=False)

        print("Page "+str(i)+" completed")
        
        return keywords

async def how_many_pages(search_key: str, year_from: str, year_to: str):
    #collect the number of items, calc the number of pages to browse through.
    num_pages = 0
    async with async_playwright() as playwright:
        init_page = await open(playwright)
        await init_page.goto("https://ieeexplore.ieee.org/search/searchresult.jsp?queryText="+search_key+"&highlight=false&returnType=SEARCH&matchPubs=true&sortType=newest&rowsPerPage=100&ranges="+year_from+"_"+year_to+"_Year&returnFacets=ALL&pageNumber=1", timeout = 0)
        await init_page.wait_for_timeout(10000)
        
        results = await init_page.query_selector_all('span.strong')
        results_str = await results[1].inner_text()
        num_results = int(results_str.replace(',', ''))
    num_pages = int(num_results/100)+1
    print("Number of search results pages : "+str(num_pages))
    return num_pages

    
async def main():
    print("\nExploring IEEE Xplore\n")
    search_key = input("Input the search keyword (currently only available for 'blockchain'): ")

    option_picked = int(input("Which procedure would you wish to work on? (enter a number)\n[1] Collect basic infos\n[2] Yearly keywords\n[3] Top authors (from the output of [1])\n[4] Yearly trends (from the output of [2])\n"))
    if (option_picked == 1) :
        year_from = input("Year range from (year) : ")
        year_to = input("Year range to (year) : ")

        if (year_to < year_from):
            print("Error in year range")
            return
        else:
            num_pages = await how_many_pages(search_key, year_from, year_to)
            end_range = int(num_pages/20) + 2

            #start collecting
            for i in range (1, end_range):
                await task_handler1(i, num_pages, search_key, year_from, year_to)

    elif (option_picked == 2) :
        year_at = input("Pick a specific year collect keywords :")
        num_pages = await how_many_pages(search_key, year_at, year_at)

        keywords = []
        for i in range (1, num_pages + 1):
            part_keywords = await task_handler2(i, search_key, year_at)
            keywords.append(part_keywords)

    elif (option_picked == 3) :
        data = pd.read_csv("basic_infos.csv")
        authors_raw = data['authors'].tolist()
        authors = []
        for item in authors_raw:
            splited = str(item).split(";")
            for author in splited:
                authors.append(author)
        
        #remove the items that do not have any author
        authors = [str(val) for val in authors]
        authors = [val for val in authors if ((val != 'nan') and (val != ''))]

        author_counts = Counter(authors)
        trend_authors = author_counts.most_common(10)
        print(trend_authors)

    elif (option_picked == 4) :
        keywords = genfromtxt('keywords.txt', delimiter='\n', dtype=None, encoding="utf8")

        #force lowercase
        keywords = list(map(lambda x: x.lower(), keywords))
        
        #replace redundant(repeated or duplicated) words to a single word
        keywords = list(map(lambda x: x.replace('blockchains', 'blockchain'), keywords))

        keywords = list(map(lambda x: x.replace('contracts', 'smart contract'), keywords))
        keywords = list(map(lambda x: x.replace('smart contracts', 'smart contract'), keywords))

        keywords = list(map(lambda x: x.replace('internet of things (iot)', 'internet of things'), keywords))
        keywords = list(map(lambda x: x.replace('iot', 'internet of things'), keywords))

        #delete search keyword (blockchain) from the list
        keywords = [val for val in keywords if (val != 'blockchain')]
        
        keyword_counts = Counter(keywords)
        trend_keywords = keyword_counts.most_common(10)
        print(trend_keywords)


    else:
        print("Wrong input")
        return

asyncio.run(main())