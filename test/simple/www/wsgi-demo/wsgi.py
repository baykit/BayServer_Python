from wsgi_demo import WsgiDemo

def application(env, start_response):
    return WsgiDemo()(env, start_response)




