FROM python:2.7
RUN apt update
COPY . /ProfileService
WORKDIR /ProfileService
ADD requirements.txt /ProfileService/requirements.txt
RUN pip install -r /ProfileService/requirements.txt
EXPOSE 4003
ENTRYPOINT ["python"]
CMD ["profile.py"]