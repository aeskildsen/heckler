(
// Set up the preProcessor to submit every evaluated block to the server over OSC
n = NetAddr("localhost", 5005);
this.preProcessor = {
	arg code;
	n.sendMsg('/code', code);
	code;
};
)

s.options.numOutputBusChannels_(8)
s.boot;

// Make some noise...
Ndef.clear
Ndef.defaultFadeTime = 4
Ndef.gui

(
Ndef(\noise, {
	var lfo = PinkNoise.ar * LFPulse.kr(10).lag(0.01) * 12;
	Pulse.ar(LFNoise2.kr(0.5).exprange(110, 160).round(12)* LFTri.kr(0.5).pow(4).unipolar(24).midiratio * lfo.midiratio);
}).play;
)

(
Ndef(\noise, {
	var note = LFSaw.kr(0.1).cubed.unipolar(24).round(2);
	RLPF.ar(
		PinkNoise.ar,
		SinOsc.kr(10).exprange(220, 240) * note.midiratio,
		0.1
	)
}).play;
)

Ndef(\noise, {0;})
Ndef(\noise).fadeTime_(4)

TempoClock.tempo = 123/60

(
~phrase = "AAUditorium".ascii % 8;
Pdef(\piano,Pbind(
	\degree, Pshuf([~phrase, \rest].flat, inf).stutter(2),
	\dur, Pseq([
		(~phrase + 1) / 8,
		Rest(1)
	].flat, inf).stutter(2),
	\db, Pbrown(-30, -10, 1),
	\pan, Pgauss(0.0, 0.1),
	\octave, Pseq([5, [4,6]], inf),
	\root, Pwhite(-2, 4).stutter(4),
)).play;
)

Pdef(\piano).stop
Pdef(\beep).stop

(
Pdef(\beep,
	Pbind(
		\dur, Pexprand(0.1, 1),
		\legato, 0.1,
		\instrument, \default,
		\degree, Pseq([-2, 0, 4, 6], inf),
		\root, [4, 7, 11],
		\octave, 5,
	)
).play;
)

(
Ndef(\drumz,
	Pbind(
		\instrument, \slice,
		\numSlices, 16,
		\slice, Pwhite(0, 15),
		\dur, 1/16 * 4
	)
).play;
)