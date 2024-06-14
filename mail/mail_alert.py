import subprocess
import os

# Function that send email.
def send_mail(body, env, status, to):
    ''' send mail through mailx based on python environment'''
    grafana_dashboard_url = os.environ["GRAFANA_DASHBORD_URL"]
    body = "Monitoring [ES Team Dashboard on export application]'\n\t' \
        - Grafana Dashboard URL : {}'\n\t' \
        - Enviroment: {}'\n\t' \
        - Status: {}'\n\t' \
        - Alert Message : {} \
        ".format(grafana_dashboard_url, env, status, body)
    
    email_user_list = to.split(",")
    print(f"email_user_list : {email_user_list}")
    """
    for user in email_user_list:
        print(user)
        cmd=f"echo {body} | mailx -s 'Prometheus Monitoring Alert' " + "-c a@test.mail " + to
        result = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        output, errors = result.communicate()
        if output:
            print(f"Send mail to user : {user}, output : {output}")
        if errors:
            print(errors)
    """

    # cmd=f"echo {body} | mailx -s 'Prometheus Monitoring Alert' " + "-c a@test.mail " + to
    cmd=f"echo {body} | mailx -s 'Prometheus Monitoring Alert' " + to
    result = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
    output, errors = result.communicate()
    if output:
        print(f"Send mail output : {output}")
    if errors:
        print(errors)
    

if __name__ == '__main__':
    # Send Email
    body_text = "all Kafka listeners are not active process running.."
    
    email_list = os.environ["EMAIL_LIST"]
    print(f"mail_list : {email_list}")
    ''' Call function to send an email'''
    send_mail(body=body_text, env='Dev', status='Yellow', to=email_list)