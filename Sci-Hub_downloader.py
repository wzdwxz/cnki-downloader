import requests
from bs4 import BeautifulSoup
import re
import time

class SciHubDownloader:
    def __init__(self):
        self.scihub_links = []
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36'
        })
    
    def get_scihub_links(self):
        """从工具网站获取可用的Sci-Hub链接"""
        try:
            response = self.session.get('https://tool.yovisun.com/scihub/')
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            # 查找包含Sci-Hub链接的元素
            links_div = soup.find('div', class_='links')
            if not links_div:
                # 尝试其他常见的类名或结构
                links_div = soup.find('div', string=re.compile(r'sci-hub', re.I))
                if not links_div:
                    # 尝试查找所有包含sci-hub的链接
                    all_links = soup.find_all('a', href=True)
                    self.scihub_links = [
                        link['href'] for link in all_links 
                        if 'sci-hub' in link['href'].lower()
                    ]
                    return self.scihub_links
            
            # 如果找到links div，则提取其中的链接
            links = links_div.find_all('a', href=True)
            self.scihub_links = [link['href'] for link in links if 'sci-hub' in link['href'].lower()]
            
            # 如果上述方法都没有找到链接，尝试正则表达式搜索
            if not self.scihub_links:
                pattern = r'https?://[^\s"<>\[\]]*sci-hub[^\s"<>\[\]]*'
                matches = re.findall(pattern, response.text, re.IGNORECASE)
                self.scihub_links = list(set(matches))  # 去重
                
            return self.scihub_links
        except Exception as e:
            print(f"获取Sci-Hub链接失败: {e}")
            return []
    
    def find_working_link(self):
        """测试可用的Sci-Hub链接"""
        if not self.scihub_links:
            self.get_scihub_links()
        
        for link in self.scihub_links:
            try:
                # 确保链接格式正确
                if not link.startswith(('http://', 'https://')):
                    link = 'https://' + link
                elif link.startswith('//'):
                    link = 'https:' + link
                
                # 测试链接是否可用
                test_response = self.session.head(link, timeout=10)
                if test_response.status_code == 200:
                    print(f"找到可用的Sci-Hub链接: {link}")
                    return link
            except Exception:
                continue
        
        print("没有找到可用的Sci-Hub链接")
        return None
    
    def download_paper(self, identifier, output_path=None):
        """
        下载论文
        :param identifier: DOI, PMID, 或文章URL
        :param output_path: 保存路径
        """
        working_link = self.find_working_link()
        if not working_link:
            print("无法找到可用的Sci-Hub链接，下载失败")
            return False
        
        try:
            # 构造下载URL
            download_url = f"{working_link.strip('/')}/{identifier}"
            
            print(f"正在从 {download_url} 下载...")
            response = self.session.get(download_url, timeout=30)
            response.raise_for_status()
            
            # 尝试从响应中提取PDF下载链接
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 查找PDF iframe 或直接的PDF链接
            pdf_frame = soup.find('iframe', {'src': re.compile(r'\.pdf')})
            if pdf_frame:
                pdf_url = pdf_frame['src']
                if pdf_url.startswith('//'):
                    pdf_url = 'https:' + pdf_url
                elif not pdf_url.startswith(('http://', 'https://')):
                    if working_link.endswith('/'):
                        pdf_url = working_link + pdf_url.lstrip('/')
                    else:
                        pdf_url = working_link + '/' + pdf_url.lstrip('/')
                
                # 下载PDF
                pdf_response = self.session.get(pdf_url, timeout=30)
                pdf_response.raise_for_status()
                
                if output_path is None:
                    # 尝试从Content-Disposition头获取文件名
                    content_disposition = pdf_response.headers.get('content-disposition')
                    if content_disposition:
                        filename_match = re.search(r'filename="?(.*?)"?', content_disposition)
                        if filename_match:
                            output_path = filename_match.group(1)
                    if not output_path:
                        output_path = "paper.pdf"
                
                with open(output_path, 'wb') as f:
                    f.write(pdf_response.content)
                
                print(f"论文已成功下载至: {output_path}")
                return True
            
            # 如果没有找到iframe，检查是否有直接的PDF链接
            pdf_links = soup.find_all('a', href=re.compile(r'\.pdf'))
            for link in pdf_links:
                pdf_url = link['href']
                if pdf_url.startswith('//'):
                    pdf_url = 'https:' + pdf_url
                elif not pdf_url.startswith(('http://', 'https://')):
                    continue
                
                pdf_response = self.session.get(pdf_url, timeout=30)
                pdf_response.raise_for_status()
                
                if output_path is None:
                    output_path = "paper.pdf"
                
                with open(output_path, 'wb') as f:
                    f.write(pdf_response.content)
                
                print(f"论文已成功下载至: {output_path}")
                return True
            
            print("未找到PDF下载链接")
            return False
            
        except Exception as e:
            print(f"下载失败: {e}")
            return False
    
    def search_and_download(self, query, output_path=None):
        """通过查询词搜索并下载论文"""
        # 这里可以集成学术搜索引擎API
        # 为了示例，我们假设传入的是DOI
        return self.download_paper(query, output_path)

def main():
    downloader = SciHubDownloader()
    
    print("正在获取可用的Sci-Hub链接...")
    links = downloader.get_scihub_links()
    print(f"找到 {len(links)} 个潜在链接: {links[:5]}...")  # 显示前5个
    
    # 示例：下载一篇论文 (使用DOI)
    doi = input("请输入论文DOI、PMID或URL: ").strip()
    if doi:
        success = downloader.download_paper(doi)
        if success:
            print("下载完成！")
        else:
            print("下载失败！")

if __name__ == "__main__":
    main()
