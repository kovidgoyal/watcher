" Scan the following dirs recursively for tags
let g:project_tags_dirs = ['watcher']
let g:ycm_python_binary_path = 'python'
set wildignore+==template.py
set wildignore+=tags

python3 <<endpython
import sys
sys.path.insert(0, os.path.abspath('.'))
import watcher
endpython
