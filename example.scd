(
// Set up the preProcessor to submit every evaluated block to the server over OSC
n = NetAddr("localhost", 5005);
this.preProcessor = {
	arg code;
	n.sendMsg('/code', code)
}
)


s.boot;

(
// Make some noise...
{
	PinkNoise.ar * 0.1
}.play;
)