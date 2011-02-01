#!/usr/bin/env perl

use strict;
use warnings;
use File::Stat qw(:all);
use File::Basename;
use YAML::Syck;

my $kernel_path = "/data/bancroft/tapper/live/repository/packages/kernel/";


our $temarepath="/home/tapper/temare";
$ENV{PYTHONPATH}=$ENV{PYTHONPATH} ? $ENV{PYTHONPATH}.":$temarepath/src" : "$temarepath/src";
our $tapperpath="/home/tapper/perl510/";
our $execpath="$tapperpath/bin";
our $grub_precondition=14;
our %hostliste = ("athene" => 1,
                  "kobold" => 1,
                  "satyr"  => 1,
                  "lemure" => 1);
my $filename          = "/tmp/temare_metainfo.yml";
my $precondition_file = "/tmp/temare_precondition.yml";


sub gen_xen
{
        my ($host)           = @_;
        $ENV{TAPPER_TEMARE} = $filename;
        my $precondition     = qx($temarepath/temare subjectprep $host);
        return if $?;
        my $config           = LoadFile($filename);
        my $precond_id;

        if ($config) {
                open (FH,">","$precondition_file") or die "Can't open $precondition_file:$!";
                print FH $precondition;
                close FH or die "Can't write $filename:$!";
                open(FH, "$execpath/tapper-testrun newprecondition --condition_file=$precondition_file|") or die "Can't open pipe:$!";
                $precond_id = <FH>;
                chomp $precond_id;
        }

        my $subject = $config->{subject};
        my $testrun;
        if ($config->{subject} =~ /kvm/i) {
                $testrun    = qx($execpath/tapper-testrun new --topic=$subject --precondition=$precond_id --host=$host);
                die "Can't create kvm test" if $?;
                print "KVM on $host with precondition $precond_id: $testrun";
        } else {
                $testrun    = qx($execpath/tapper-testrun new --topic=$subject --precondition=$grub_precondition --precondition=$precond_id --host=$host);
                die "Can't create xen test" if $?;
                print "Xen on $host with preconditions $grub_precondition, $precond_id: $testrun";
        }
}


sub younger
{
        my $st_a = stat($a);
        my $st_b = stat($b);
        return $st_a->mtime() <=> $st_b->mtime();
}

sub gen_kernel
{
        my ($host)          =  @_;
        my @kernelfiles     =  sort younger <$kernel_path/x86_64/*>;
        my $kernelbuild     =  pop @kernelfiles;

        my $kernel_version;
        open FH,"tar -tzf $kernelbuild|" or die "Can't look into kernelbuild:$!";
 TARFILES:
        while (my $line = <FH>){
                if ($line =~ m/vmlinuz-(.+)$/) {
                        $kernel_version = $1;
                        last TARFILES ;
                }
        }
        my $id = qx($execpath/tapper-testrun new --macroprecond=/data/bancroft/tapper/live/repository/macropreconditions/kernel/kernel_boot.mpc --hostname=$host -Dkernel_version=$kernel_version -Dkernelpkg=$kernelbuild --owner=mhentsc3 --topic=Kernel);
        print "Kernel testrun on $host: $id";
}



# randomly define the one host that runs a kernel test
my $random = int(rand((scalar keys %hostliste) - 1));
my $count  = 0;

HOST:
foreach my $host (keys %hostliste) {
        next HOST if not $hostliste{$host};
        if ($count == $random) {
                gen_kernel($host);
        } else {
                gen_xen($host);
        }
        $count++;
}
