# Setup instructions

* Install (https://virtualenv.pypa.io)[virtualenv] globally
* Create a virtual environment in the directory up from this one
e.g.
```
cd ..
virtualenv venv
```
Inside this repo run:
```
./setup
`

You'll need to setup a channel key inside ifttt.cfg

```
CHANNEL_KEY='my-secret'
```
# Running

Get the server up and running you can edit app.py and uncomment the debug lines.

```
source ../venv/bin/activate
python app.py
```

Send a post request to verify things are working:
```
curl -d "" -X POST http://localhost:5000/v1/test/setup
curl -d "" -X POST http://localhost:5000/v1/triggers/picture_of_the_day
```

# Triggers

Triggers are defined in ifttt/triggers.py
Triggers are exposed at http://localhost:5000/v1/triggers/<trigger name>
	where trigger name is either explicitly added via url_pattern or generated from the class name in snake case. e.g. PictureOfTheDay becomes picture_of_the_day

A trigger is either JSON based (BaseTriggerView) or feed based (BaseFeaturedFeedTriggerView)

Create a trigger in ifttt/triggers.py and expose it in ifttt/core.py

## Trigger fields

Trigger fields can be customised like so:

```
curl -H "Content-Type: application/json"  -d '{"triggerFields":{"hrs":"2"}}' -X POST http://localhost:5000/v1/triggers/trending_topics
```

## Channel config

Note the channel_config.yaml file needs to be manually loaded into IFTTT. It lives in this repo purely for tracking purposes.

