Forumposter lets you auto-post data (such as ranked movies) in 
CSV format to a zetaboards forum.

The script takes a CSV file as input and transforms it so 
it can be rendered with [jinja2 templates](http://jinja.pocoo.org/).

1) Edit the config.ini file (rename config.ini.example -> config.ini 
if using the Python script)  
2) Modify the template  
3) Run the script/executable

So if your CSV looks like this (note that a header is always required):

"rank","movie","score"  
"1","Citizen Kane","155"  
"2","2001: A Space Odyssey","120"  
...  
"100","Vertigo","23"

You can access these values in the template by their column header name:

{% for entry in entries %}  
{{ entry.rank }}. {{ entry.movie }} - ({{ entry.score }} points)   
{% endfor %}

And it's rendered as:

100. Vertigo - (23 points)

The default template assumes a single column called "entry".