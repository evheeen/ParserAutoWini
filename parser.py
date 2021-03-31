from selenium import webdriver
from selenium.webdriver.support.ui import Select
import mysql.connector
from mysql.connector import Error
from datetime import datetime
import requests, time, os, ftplib, pyautogui
from shutil import rmtree


def proxyAuth(username, password):
    time.sleep(0.5)
    pyautogui.typewrite(username)
    pyautogui.press('tab')
    pyautogui.typewrite(password)
    pyautogui.press('enter')


def parseAndTransfer(year, carBrand, fuelType, startPage, endPage, proxyIp):
    print(f'Parsing {fuelType} {carBrand} {year}-')
    option = webdriver.ChromeOptions()
    # option.add_argument('headless')
    option.add_argument('--ignore-certificate-errors')
    option.add_argument('--ignore-ssl-errors')
    option.add_argument(f"--proxy-server={proxyIp}")
    driver = webdriver.Chrome(options=option)
    
    driver.get('https://www.autowini.com/Cars/car-search')
    proxyAuth("login", "password")
    time.sleep(1)
    
    # Change language
    driver.execute_script("javascript:fnLangChange('ru')")
    
    # Apply filtres
    time.sleep(0.5)
    years = Select(driver.find_element_by_id('i_sStartYear'))
    years.select_by_visible_text(year)
    car = Select(driver.find_element_by_id('i_sMakeCd'))
    car.select_by_visible_text(carBrand)
    fuel = Select(driver.find_element_by_id('i_sFuelTypeCd'))
    fuel.select_by_visible_text(fuelType)
    driver.execute_script('javascript:fnLeftSearch()')
    time.sleep(1.5)
    
    links = []
    checkNone = driver.find_elements_by_class_name('boxCount')
    if len(checkNone) == 1:
        # Get links to goods
        foundResualts = driver.find_element_by_class_name('boxCount').text[16:]
        foundResualts = str.replace(foundResualts, ',', '')
        foundResualts = int(foundResualts[0:-6])
        if foundResualts < 30:
            getLinksUl = driver.find_element_by_class_name('listBox')
            getLinksLi = getLinksUl.find_elements_by_xpath('.//li')
            for li in getLinksLi:
                li = li.find_element_by_xpath('.//a')
                links.append(li.get_attribute('href'))
            print('Found ', len(links), 'goods')
            if len(links) > 0:
                parse(links, driver)
        else:
            if startPage > endPage:
                startPage, endPage = endPage, startPage
            if (endPage * 30 + 30) >= foundResualts:
                endPage = int(round(foundResualts / 30, 0) + 1)
            time.sleep(0.5)
            driver.execute_script(f"javascript:CmPageMove({startPage})")
            for page in range(endPage - startPage + 1):
                getLinksUl = driver.find_element_by_class_name('listBox')
                getLinksLi = getLinksUl.find_elements_by_xpath('.//li')
                for li in getLinksLi:
                    li = li.find_element_by_xpath('.//a')
                    links.append(li.get_attribute('href'))
                driver.execute_script(f"javascript:CmPageMove('{startPage + page + 1}')")
            print('Found ', len(links), 'goods')
            if len(links) > 0:
                parse(links, driver)
    elif len(checkNone) == 0:
        print(f'{carBrand} in this configuration is not found')
    
    time.sleep(2)
    driver.quit()


# Download images and transfer via FTP and  MySQL
def imagesFTP(links, dirName, connect, lastId):
    path = os.getcwd() + "\\temp\\" + dirName
    try:
        os.mkdir(path)
    except OSError as er:
        print('Creation directory for load images failed\nError:', er)
    else:
        print('\tDirectory created')
        for link in links:
            index = links.index(link) + 1
            r = requests.get(link, allow_redirects=True)
            open(f"{path}\\{dirName}({index}).jpg", "wb").write(r.content)
            try:
                fileToSend = open(f'{path}\\{dirName}({index}).jpg', "rb")
                with ftplib.FTP(host="host", user="username", passwd="password") as ftp:
                    ftp.cwd('/img/uploads/prebg/')
                    ftp.storbinary(f'STOR {dirName}({index}).jpg', fileToSend)
                    ftp.close()
                fileToSend.close()
                
                addImage = f"INSERT INTO `ns_images`(`itemId`, `number`, `previewsm`, `previewmed`, `previewbg`)" \
                           f"VALUES ({lastId}, {index}, 'img//uploads//prebg//{dirName}({index}).jpg', 'img//uploads//prebg//{dirName}({index}).jpg', 'img//uploads//prebg//{dirName}({index}).jpg')"
                executeQuery(connect, addImage, f'Image {index}')
            except Exception as e:
                print('Error:', e)
        try:
            rmtree(path, ignore_errors=True)
        except Exception as exc:
            print('Warning:', exc)


def parse(links, driver):
    connect = mysqlConnecting()
    for link in links:
        # Search and copy information
        driver.get(link)
        tableInfo = driver.find_element_by_class_name('infoArea')
        markaDB = tableInfo.find_element_by_xpath('.//table/tbody/tr[2]/td[1]').text
        modelDB = tableInfo.find_element_by_xpath('.//table/tbody/tr[3]/td').text
        carClass = tableInfo.find_element_by_xpath('.//table/tbody/tr[4]/td').text
        nameDB = modelDB + ' ' + carClass
        yearManDB = tableInfo.find_element_by_xpath('.//table/tbody/tr[2]/td[2]').text
        carType = tableInfo.find_element_by_xpath('.//table/tbody/tr[1]/td[2]').text
        engineCapacityDB = tableInfo.find_element_by_xpath('.//table/tbody/tr[6]/td[1]').text
        engineTypeDB = tableInfo.find_element_by_xpath('.//table/tbody/tr[7]/td[2]').text
        driveTypeDB = tableInfo.find_element_by_xpath('.//table/tbody/tr[9]/td[2]').text
        transmissionDB = tableInfo.find_element_by_xpath('.//table/tbody/tr[7]/td[1]').text
        mileageDB = tableInfo.find_element_by_xpath('.//table/tbody/tr[5]/td').text
        price = driver.find_element_by_id('itemBisPrice').text
        vin = driver.find_element_by_class_name('subInfo').find_element_by_xpath('.//span[1]').text
        vin = str.replace(vin, 'Номер товара: ', '')
        
        mileage = ''
        if mileageDB == '- км (не оригинал) !':
            mileageDB = 'Пробег уточняйте у менеджера'
            mileage = 'Пробег уточняйте у менеджера'
        
        options = driver.find_elements_by_class_name('conOption')
        textDB = ' '
        if len(options) != 0:
            optOne = options[0].find_elements_by_xpath('.//ul/li[1]/div/span')
            optTwo = options[0].find_elements_by_xpath('.//ul/li[2]/div/span')
            optThree = options[0].find_elements_by_xpath('.//ul/li[3]/div/span')
            bodyOprions = ''
            bodyTwoOptions = ''
            salonOptions = ''
            for opt in optOne:
                bodyOprions += ('<dd><span class="t">' + opt.text + '</span></dd>')
            for opt in optTwo:
                bodyTwoOptions += ('<dd><span class="t">' + opt.text + '</span></dd>')
            for opt in optThree:
                salonOptions += ('<dd><span class="t">' + opt.text + '</span></dd>')
            bodyOprions = f"<dl><dt class=\"dttle\">{mileage}</dt><dt class=\"dttle\">Опции кузова</dt>" + bodyOprions + "</dl>"
            bodyTwoOptions = "<dl class=\"box bx01\"><dt class=\"dttle\">Опции кузова</dt>" + bodyTwoOptions + "</dl>"
            salonOptions = "<dl class=\"box bx02\"><dt class=\"dttle\">Опции салона</dt>" + salonOptions + "</dl>"
            textDB = bodyOprions + bodyTwoOptions + salonOptions
        
        # Images
        images = []
        imagesUl = driver.find_element_by_class_name('detailImg').find_element_by_class_name(
            'thumbWrap').find_element_by_xpath('.//ul')
        imagesLi = imagesUl.find_elements_by_xpath('.//li')
        for li in imagesLi:
            li = li.find_element_by_xpath('.//a/img')
            imgFormat = str.replace(li.get_attribute('src'), '_1024', '_')
            imgFormat = str.replace(imgFormat, '_320', '_')
            images.append(imgFormat)
        
        # Video
        videoA = driver.find_element_by_class_name('detailImg').find_elements_by_class_name('btnVideo')
        videoError = driver.find_elements_by_class_name('ytp-error-content-wrap-reason')
        if len(videoA) > 0:
            if len(videoA) == 0:
                videoA[0].click()
                videoUrl = driver.find_element_by_class_name('detail_Youtube').get_attribute('src')
                videoUrl = str.replace(videoUrl, '&autoplay=1', '&autoplay=0')
                driver.execute_script('javascript:youtubePopClose()')
        else:
            videoUrl = ''
        
        # DateTimeStamp
        timeNow = str(datetime.now())
        
        # Formatting
        chars = ''
        URL = markaDB + '-' + modelDB + '-' + yearManDB
        URL = str.replace(URL, '+', '-')
        URL = str.replace(URL, '.', '-')
        URL = str.replace(URL, ' ', '-')
        modelDB = str.replace(modelDB, 'All NEW ', '')
        modelDB = str.replace(modelDB, 'All New ', '')
        modelDB = str.replace(modelDB, 'All NEW', '')
        modelDB = str.replace(modelDB, 'All New', '')
        modelDB = str.replace(modelDB, 'New ', '')
        modelDB = str.replace(modelDB, 'All ', '')
        nameDB = str.replace(nameDB, 'All NEW ', '')
        nameDB = str.replace(nameDB, 'All New ', '')
        nameDB = str.replace(nameDB, 'All NEW', '')
        nameDB = str.replace(nameDB, 'All New', '')
        nameDB = str.replace(nameDB, 'New ', '')
        nameDB = str.replace(nameDB, 'All ', '')
        price = str.replace(price, 'USD ', '')
        price = float(str.replace(price, ',', ''))
        
        if carType == 'Sedan':  # carType = 'Седан'
            chars += '|69|'
        elif carType == 'SUV':  # carType = 'Кроссовер'
            chars += '|66|'
        elif carType == 'Van/MiniVan':  # carType = 'Минивэн'
            chars += '|68|'
        elif carType == 'Hatchback':
            carType = 'Хэтчбек'
        elif carType == 'Convertible':  # carType = 'Кабриолет'
            chars += '|65|'
        
        if engineTypeDB == 'Gasoline':
            engineTypeDB = 'Бензин'
            chars += '|79|'
        elif engineTypeDB == 'LPG':
            engineTypeDB = 'Газ'
            chars += '|82|'
        
        if transmissionDB == 'Automatic':
            transmissionDB = 'Автомат'
            chars += '|31|'
        elif transmissionDB == 'Manual':
            transmissionDB = 'Механика'
            chars += '|32|'
        
        if driveTypeDB == 'Front 2WD':
            driveTypeDB = 'Передний'
            chars += '|72|'
        elif driveTypeDB == '4 Wheel Drive':
            driveTypeDB = 'Полный'
            chars += '|73|'
        elif driveTypeDB == 'Rear 2WD':
            driveTypeDB = 'Задний'
            chars += '|71|'
        
        # filterParamId
        if markaDB == 'Kia':  # Car Brand
            chars += '|86|'
        if markaDB == 'Hyundai':
            chars += '|85|'
        if markaDB == 'Toyota':
            chars += '|115|'
        if markaDB == 'Lexus':
            chars += '|107|'
        if markaDB == 'Genesis':
            chars += '|93|'
        
        engineCapacityDB = engineCapacityDB[:-2]
        engineCapacityDB = str.replace(engineCapacityDB, ' ', '')
        engineCapacityDB = round(float(str.replace(engineCapacityDB, ',', '.')), 1)
        if engineCapacityDB == 998.0:
            engineCapacityDB = 1.0
        
        print('Parsing', markaDB, modelDB, yearManDB)
        
        # Adding cars to your database
        # Example
        insertQuery = f"INSERT INTO `ns_goods`" \
                      f"(`topItem`, `tree`, `parent`, `visible`, `url`, `mainImage`, `popular`, `name`, `number`, `title`, `description`, `keywords`, `mainPrice`, `priceAllin`, `code`, `chars`, `brandId`, `price`, `units`, `info`, `textRight`, `text`, `changefreq`, `lastmod`, `priority`, `startPrice`, `valuteId`, `attributes`, `newItem`, `actPrice`, `startActPrice`, `attrPrice`, `actAttrPrice`, `mainAttrPrice`, `tree1`, `statusId`, `supplierCode`, `zakPrice`, `supplierId`, `upload`, `canBuy`, `quantity`, `percent`, `actionTime`, `actDate`, `actTime`, `tempid`, `colcom`, `rating`, `inOrder`, `marka`, `model`, `engineType`, `engineСapacity`, `mileage`, `transmission`, `driveType`, `yearMan`) " \
                      f"VALUES(1, '|96|', 96, 1, '{URL + vin}', 'img//uploads//prebg//{URL + vin}(1).jpg', 0, '{nameDB}', 100, '', '', '', {price}, '{videoUrl}', '{vin}', '{chars}', 0, {price}, '', '', '', '{textDB}', 'always', '{timeNow}', 0.9, {price}, 1, '', 1, 0, 0, {price}, 0, {price}, '|96|', 7, '', 0, 0, 0, 1, 0, 0, 0, 0, '', '', 0, 0, 0, '{markaDB}', '{modelDB}', '{engineTypeDB}', '{engineCapacityDB}', 0, '{transmissionDB}', '{driveTypeDB}', '{yearManDB}')"
        executeQuery(connect, insertQuery, 'Row')
        
        getLastId = f"SELECT * FROM `ns_goods` ORDER BY `itemId` DESC LIMIT 1"
        lastId = (readQuery(connect, getLastId))[0][0]
        
        categoryQuery = f"INSERT INTO `ns_itemcatlink`(`categoryId`, `itemId`)" \
                        f"VALUES (96, {lastId})"
        executeQuery(connect, categoryQuery, 'Category')
        
        menuQuery = f"INSERT INTO `ns_sititem`(`name`, `param`, `itemId`, `bodyId`) " \
                    f"VALUES ('overhead1', 'chaptersMenu', {lastId}, '')"
        executeQuery(connect, menuQuery, 'Menu item')
        
        menuQuery = f"INSERT INTO `ns_sititem`(`name`, `param`, `itemId`, `bodyId`) " \
                    f"VALUES ('megamenu', 'megaMenu', {lastId}, '')"
        executeQuery(connect, menuQuery, 'Menu item')
        
        filterQuery = f"INSERT INTO `ns_textparam`(`filterId`, `itemId`, `text`, `textInt`)" \
                      f"VALUES (28, {lastId}, '{engineCapacityDB}', {engineCapacityDB})"
        executeQuery(connect, filterQuery, 'Filter engineCapacity')
        
        filterQuery = f"INSERT INTO `ns_textparam`(`filterId`, `itemId`, `text`, `textInt`)" \
                      f"VALUES (24, {lastId}, '{yearManDB}', {int(yearManDB)})"
        executeQuery(connect, filterQuery, 'Filter yearMan')
        
        filterQuery = f"INSERT INTO `ns_textparam`(`filterId`, `itemId`, `text`, `textInt`)" \
                      f"VALUES (32, {lastId}, '{carClass}', 0)"
        executeQuery(connect, filterQuery, 'Filter completation')
        
        imagesFTP(images, URL + vin, connect, lastId)


def mysqlConnecting():
    connection = None
    try:
        connection = mysql.connector.connect(
            host='host',
            user='userName',
            passwd='password',
            database='databaseName'
        )
        print('MySQL Database connection successful')
    except Error as err:
        print(f"Error: {err}")
    return connection


def readQuery(connection, query):
    cursor = connection.cursor()
    try:
        cursor.execute(query)
        result = cursor.fetchall()
        return result
    except Error as err:
        print(f"Error: {err}")


def executeQuery(connection, query, str):
    cursor = connection.cursor()
    try:
        cursor.execute(query)
        connection.commit()
        print(f"\t{str} added")
    except Error as err:
        print(f"Error: {err}")


def parsing():
    proxies = ['ip:port']  # , ... , ... , ...]
    carBrand = input('Enter car brand Hyundai/Kia/Genesis/Toyota/Lexus: ')
    fuelType = input('Enter fuel type Gasoline/LPG: ')
    startPage = int(input('Enter start page: '))
    endPage = int(input('Enter end page: '))
    try:
        parseAndTransfer('2018', carBrand, fuelType, startPage, endPage, proxies[0])
        print('\nParsing completed')
    
    except Exception as error:
        print('\nError:', error)
        # try:
        #     parseAndTransfer('2018', carBrand, fuelType, startPage, endPage, proxies[1])
        #     print('\nParsing completed')
        #
        # except Exception as error:
        #     print('\nError:', error)
        #     try:
        #         parseAndTransfer('2018', carBrand, fuelType, startPage, endPage, proxies[2])
        #         print('\nParsing completed')
        #
        #     except Exception as error:
        #         print('\nError:', error)


if __name__ == '__main__':
    parsing()