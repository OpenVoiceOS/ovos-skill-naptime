# <img src='https://raw.githack.com/FortAwesome/Font-Awesome/master/svgs/solid/bed.svg' card_color='#22a7f0' width='50' height='50' style='vertical-align:bottom'/> Naptime

Put the assistant to sleep when you don't want to be disturbed.

## About

Tell the assistant to sleep when you don't want to be disturbed in any way.
This stops all calls to Speech to Text system, guaranteeing your voice won't be sent anywhere on an accidental activation.

When sleeping, the assistant will only listen locally for the wake word `Hey Mycroft, wake up`. Otherwise the system will be totally silent and won't bother you.

On a Mark 1 device this also dims the eyes.

Skill can mute the audio as well when entering into sleep mode if required.

## Configuration

The skill utilizes the `~/.config/mycroft/skills/ovos-skill-naptime.openvoiceos/settings.json` file which allows you to configure this skill.

```json
{
  "mute": false
}
```

## Examples

- "Go to sleep"
- "Nap time"
- "Wake up"

## Credits

OpenVoiceOS (@OpenVoiceOS)
Mycroft AI (@MycroftAI)

## Category

**Daily**
Configuration

## Tags

#nap
#naptime
#sleep
#donotdisturb
#do-not-disturb
