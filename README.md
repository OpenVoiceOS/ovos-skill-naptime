# <img src='https://raw.githack.com/FortAwesome/Font-Awesome/master/svgs/solid/bed.svg' card_color='#22a7f0' width='50' height='50' style='vertical-align:bottom'/> Naptime

Put the assistant to sleep when you do not want it to listen.

## About

Naptime tells the assistant to stop listening for commands. This stops all calls to the speech-to-text system, so your voice cannot be sent anywhere by an accidental activation.

While sleeping, the assistant only listens locally for the wake word "Hey Mycroft, wake up". Otherwise the system stays silent.

On a Mark 1 device, sleep mode also dims the eyes.

The skill can also mute the audio when it enters sleep mode, if you configure it to do so.

## Configuration

The skill uses the `~/.config/mycroft/skills/ovos-skill-naptime.openvoiceos/settings.json` file. Set `mute` to `true` to mute the audio when the assistant goes to sleep.

```json
{
  "mute": false
}
```

## Examples

- "Go to sleep"
- "Nap time"
- "Wake up"

## Related projects

- [OpenVoiceOS/ovos-core](https://github.com/OpenVoiceOS/ovos-core) — the assistant core that this skill plugs into.
- [OpenVoiceOS/ovos-workshop](https://github.com/OpenVoiceOS/ovos-workshop) — the skill framework this skill is built on.

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
