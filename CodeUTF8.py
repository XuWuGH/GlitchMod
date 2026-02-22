#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import json
import chardet
import re
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# 线程锁用于输出同步
output_lock = threading.Lock()
json_lock = threading.Lock()

def detect_encoding(file_path):
    """检测文件编码"""
    with open(file_path, 'rb') as f:
        raw_data = f.read()
        result = chardet.detect(raw_data)
        encoding = result['encoding']
        if encoding is None:
            encoding = 'utf-8'
        return encoding

def get_file_size(file_path):
    """获取文件大小（字节）"""
    return os.path.getsize(file_path)

def remove_comments(content):
    """删除C/C++代码中的注释"""
    result = []
    i = 0
    in_multiline_comment = False
    in_string = False
    string_char = None
    escaped = False
    
    while i < len(content):
        char = content[i]
        
        if escaped:
            escaped = False
            result.append(char)
            i += 1
            continue
        
        if char == '\\' and in_string:
            escaped = True
            result.append(char)
            i += 1
            continue
        
        # 处理字符串
        if not in_multiline_comment and (char == '"' or char == "'"):
            if not in_string:
                in_string = True
                string_char = char
            elif char == string_char:
                in_string = False
                string_char = None
            result.append(char)
            i += 1
            continue
        
        # 如果在字符串中，直接添加字符
        if in_string:
            result.append(char)
            i += 1
            continue
        
        # 处理多行注释开始 /*
        if i < len(content) - 1 and content[i:i+2] == '/*' and not in_multiline_comment:
            in_multiline_comment = True
            i += 2
            continue
        
        # 处理多行注释结束 */
        if i < len(content) - 1 and content[i:i+2] == '*/' and in_multiline_comment:
            in_multiline_comment = False
            i += 2
            continue
        
        # 如果在多行注释中，跳过字符
        if in_multiline_comment:
            i += 1
            continue
        
        # 处理单行注释 //
        if i < len(content) - 1 and content[i:i+2] == '//':
            # 找到行尾
            while i < len(content) and content[i] != '\n':
                i += 1
            # 不添加换行符，因为下一行会处理
            continue
        
        # 正常字符
        result.append(char)
        i += 1
    
    # 将结果按行分割处理
    processed_lines = []
    for line in ''.join(result).split('\n'):
        stripped = line.strip()
        if stripped:  # 只保留非空行
            processed_lines.append(line.rstrip())
    
    return '\n'.join(processed_lines)

def convert_to_utf8_bom(file_path, source_encoding):
    """将文件转换为UTF-8带BOM编码"""
    try:
        with open(file_path, 'r', encoding=source_encoding, errors='ignore') as f:
            content = f.read()
        
        # 删除注释
        content = remove_comments(content)
        
        # 保存为UTF-8带BOM
        with open(file_path, 'w', encoding='utf-8-sig', newline='') as f:
            f.write(content)
        
        with output_lock:
            print(f"Processing: {file_path}", file=os.sys.stderr)
        
        return True
    except Exception as e:
        with output_lock:
            print(f"Error converting {file_path}: {e}", file=os.sys.stderr)
        return False

def process_file_info(file_path, script_dir, ext_type):
    """处理单个文件的信息（编码检测、大小获取）"""
    try:
        rel_path = file_path.relative_to(script_dir)
        file_info = {
            'file_name': str(rel_path).replace('\\', '/'),
            'file_size': get_file_size(file_path),
            'file_encoding': detect_encoding(file_path)
        }
        return (ext_type, file_info)
    except Exception as e:
        with output_lock:
            print(f"Error processing file info {file_path}: {e}", file=os.sys.stderr)
        return None

def search_files(script_dir):
    """使用100线程搜索所有文件"""
    cpp_files = []
    h_files = []
    c_files = []
    
    # 先收集所有文件路径
    all_file_paths = []
    for ext in ['*.cpp', '*.h', '*.c']:
        for file_path in script_dir.rglob(ext):
            if file_path.is_file():
                all_file_paths.append((file_path, ext))
    
    # 使用100线程处理文件信息
    with ThreadPoolExecutor(max_workers=100) as executor:
        futures = []
        for file_path, ext in all_file_paths:
            future = executor.submit(process_file_info, file_path, script_dir, ext)
            futures.append(future)
        
        for future in as_completed(futures):
            result = future.result()
            if result:
                ext_type, file_info = result
                if ext_type == '*.cpp':
                    cpp_files.append(file_info)
                elif ext_type == '*.h':
                    h_files.append(file_info)
                elif ext_type == '*.c':
                    c_files.append(file_info)
    
    return cpp_files, h_files, c_files

def output_json_threaded(output_json):
    """使用100线程输出JSON（分段输出）"""
    json_str = json.dumps(output_json, ensure_ascii=False, indent=2)
    lines = json_str.split('\n')
    
    # 将输出任务分配给100个线程
    def output_chunk(chunk_lines, chunk_id):
        with output_lock:
            for line in chunk_lines:
                print(line)
    
    chunk_size = max(1, len(lines) // 100)
    chunks = [lines[i:i + chunk_size] for i in range(0, len(lines), chunk_size)]
    
    with ThreadPoolExecutor(max_workers=100) as executor:
        futures = []
        for i, chunk in enumerate(chunks):
            future = executor.submit(output_chunk, chunk, i)
            futures.append(future)
        
        for future in as_completed(futures):
            future.result()

def convert_files_threaded(all_files, script_dir):
    """使用100线程转换所有文件"""
    def convert_single_file(file_info):
        file_path = script_dir / file_info['file_name']
        source_encoding = file_info['file_encoding']
        return convert_to_utf8_bom(file_path, source_encoding)
    
    with ThreadPoolExecutor(max_workers=100) as executor:
        futures = []
        for file_info in all_files:
            future = executor.submit(convert_single_file, file_info)
            futures.append(future)
        
        for future in as_completed(futures):
            future.result()

def main():
    # 获取脚本所在目录
    script_dir = Path(__file__).parent.absolute()
    
    # 使用100线程搜索所有文件
    with output_lock:
        print("Searching files with 100 threads...", file=os.sys.stderr)
    cpp_files, h_files, c_files = search_files(script_dir)
    
    # 使用100线程排序（并行排序不同列表）
    def sort_files(file_list):
        return sorted(file_list, key=lambda x: x['file_name'])
    
    with ThreadPoolExecutor(max_workers=100) as executor:
        cpp_future = executor.submit(sort_files, cpp_files)
        h_future = executor.submit(sort_files, h_files)
        c_future = executor.submit(sort_files, c_files)
        
        cpp_files = cpp_future.result()
        h_files = h_future.result()
        c_files = c_future.result()
    
    # 合并文件列表，顺序为cpp, h, c
    all_files = cpp_files + h_files + c_files
    
    # 输出JSON（使用100线程）
    output_json = {
        'files': all_files
    }
    
    with output_lock:
        print("Outputting JSON with 100 threads...", file=os.sys.stderr)
    output_json_threaded(output_json)
    
    # 使用100线程转换所有文件为UTF-8带BOM并删除注释
    with output_lock:
        print("Converting files with 100 threads...", file=os.sys.stderr)
    convert_files_threaded(all_files, script_dir)
    
    with output_lock:
        print("All files processed.", file=os.sys.stderr)

if __name__ == '__main__':
    main()
