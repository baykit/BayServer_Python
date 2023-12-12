# BayServer for Python


# 2.3.4

- [core] Addresses potential issues arising from I/O errors.
- [core] Fixes the issue encountered when aborting GrandAgent.

# 2.3.3

- [Core] Fixes a memory leak in exceptional cases.
- [CGI] Supports timeout on taxi mode.

# 2.3.2

- [Core] Fixes server crashes that sometimes occur in proxy mode with HTTP/3.

# 2.3.1

- [Core] Fixes a problem where the POST method did not work sometimes.

# 2.3.0

- [CGI] Supports "timeout" parameter. (The timed-out CGI processes are killed)
- [Core] Improves the memusage output
- [Core] Fixes some bugs

# 2.2.1

- Fixes some bugs

# 2.2.0

- Supports pip install

# 2.1.0

- Supports multi core mode for Windows
- Change name of banjo docker to "maccaferri" docker
- Fixes some bugs

# 2.0.3

- Fixes Problem of POST request which causes 404
- Translates some messages to Japanese
- Fixes potential bugs

# 2.0.2

- Fixes HTTP/2 bugs
- Fixes problem on handling wp-cron.php of WordPress
- Fixes problem on handling admin-ajax.php of WordPress
- Fixes write error when socket write buffer is full
- Fixes some bugs and syntax erros


# 2.0.1

- Modifies bayserver.plan to avoid resolving host name


# 2.0.0

- First version
